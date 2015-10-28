//
//  Kissreads2.cpp
//  discoSnp_GATB
//
//  Created by Pierre Peterlongo on 03/07/15.
//  Copyright (c) 2015 Pierre Peterlongo. All rights reserved.
//

#include <Kissreads2.h>



using namespace std;

/********************************************************************************
 *
 * A QUICK OVERVIEW OF THE CLASS...
 *
 * This class implements the detection of SNP in a provided de Bruijn graph.
 *
 * It is implemented as a subclass of Tool, so we get all the facilities of the
 * Tool class. We can therefore see two main parts here:
 *
 * 1) constructor: we define all the command line parameters available
 *
 * 2) 'execute' method: this is the main method of the class where the main loop
 *   (ie. iteration over nodes of the graph) is done.
 *
 ********************************************************************************/

/*********************************************************************
 ** METHOD  :
 ** PURPOSE :
 ** INPUT   :
 ** OUTPUT  :
 ** RETURN  :
 ** REMARKS :
 *********************************************************************/
Kissreads2::Kissreads2 () : Tool ("Kissreads2")
{
    /** We add options known by kissnp2. */
    
    getParser()->push_front (new OptionNoParam (STR_KISSREADS_GENOTYPE,             "Compute genotypes", false));
    getParser()->push_front (new OptionNoParam (STR_KISSREADS_OUTPUT_FASTA,         "Output stnadart Fasta. By default the output is formatted especially for the discoSnp++ pipeline", false));
    
    getParser()->push_front (new OptionOneParam (STR_KISSREADS_SIZE_SEEDS,          "Size of the used seeds (distinct from the size of k)",  false, "25"));
    getParser()->push_front (new OptionOneParam (STR_KISSREADS_INDEX_STRIDE,        "Index Stride", false, "2"));
    
    getParser()->push_front (new OptionOneParam (STR_KISSREADS_SIZE_K,              "Size of k, used as minial overlap and kmer spanning read coherence",  false, "31"));
//    getParser()->push_front (new OptionOneParam (STR_KISSREADS_MIN_COVERAGE,        "Minimal coverage", false, "2"));
    getParser()->push_front (new OptionOneParam (STR_KISSREADS_COVERAGE_FILE_NAME,  "File (.h5) generated by kissnp2, containing the coverage threshold per read set",  false, "_removemeplease"));
    getParser()->push_front (new OptionOneParam (STR_KISSREADS_MAX_HAMMING,         "Maximal hamming distance authorized while maping",     false, "1"));
    
    getParser()->push_front (new OptionOneParam (STR_URI_OUTPUT_COHERENT,           "Output coherent file name",                      true));
    getParser()->push_front (new OptionOneParam (STR_URI_OUTPUT_UNCOHERENT,         "Output uncoherent file name",                      true));
    getParser()->push_front (new OptionOneParam (STR_URI_READS_INPUT,               "Input reads",  true));
    getParser()->push_front (new OptionOneParam (STR_URI_PREDICTION_INPUT,          "Input predictions",  true));
    
}




/*********************************************************************
 ** METHOD  :
 ** PURPOSE :
 ** INPUT   :
 ** OUTPUT  :
 ** RETURN  :
 ** REMARKS :
 *********************************************************************/

void Kissreads2::execute ()
{
    
    IProperties* props= getInput();
    BankFasta predictions_bank = BankFasta(props->getStr(STR_URI_PREDICTION_INPUT));
    
    
    // We declare a Bank instance.
    BankAlbum banks (props->getStr(STR_URI_READS_INPUT));
    const std::vector<IBank*>& banks_of_queries = banks.getBanks();
    u_int64_t nbReads = banks.estimateNbItems();
    
    GlobalValues gv;
    gv.size_seeds=              props->getInt (STR_KISSREADS_SIZE_SEEDS);
    gv.index_stride=            props->getInt (STR_KISSREADS_INDEX_STRIDE);
    gv.minimal_read_overlap=    props->getInt (STR_KISSREADS_SIZE_K);
    gv.number_of_read_sets=     banks_of_queries.size();
    gv.subst_allowed=           props->getInt (STR_KISSREADS_MAX_HAMMING);

    // We load a Storage product "STR_KISSREADS_COVERAGE_FILE_NAME" in HDF5 format
    // It must have been created with the storage1 snippet
    Storage* storage = StorageFactory(STORAGE_HDF5).load (props->getStr (STR_KISSREADS_COVERAGE_FILE_NAME));
    LOCAL (storage);
    // Shortcut: we get the root of this Storage object
    Group& root = storage->root();
    // We get a collection of native integer from the storage.
    Collection<NativeInt64>& myIntegers = root.getCollection<NativeInt64> ("cutoffs");
    // We create an iterator for our collection.
    Iterator<NativeInt64>* iterInt = myIntegers.iterator();
    LOCAL (iterInt);
    // Now we can iterate the collection through this iterator.
    stringstream sstring_cutoffs;
    for (iterInt->first(); !iterInt->isDone(); iterInt->next())  {  gv.min_coverage.push_back(iterInt->item().toInt());  sstring_cutoffs<<iterInt->item().toInt()<<" ";}
    
    
    gv.compute_genotypes=       props->get    (STR_KISSREADS_GENOTYPE) != 0;
    gv.standard_fasta=          props->get    (STR_KISSREADS_OUTPUT_FASTA) != 0;
    
    gv.set_mask_code_seed();
    
    
    
    
    
    ofstream coherent_out;
    coherent_out.open(props->getStr(STR_URI_OUTPUT_COHERENT).c_str(),std::ofstream::out);
    
    ofstream uncoherent_out;
    uncoherent_out.open(props->getStr(STR_URI_OUTPUT_UNCOHERENT).c_str(), std::ofstream::out);
      
     
    getTimeInfo().start ("indexing");
    
    FragmentIndex index(predictions_bank.estimateNbItems());
    
    cout<<"Indexing bank "<<props->getStr(STR_URI_PREDICTION_INPUT)<<endl;
    index.index_predictions (predictions_bank, gv);       // read and store all starters presents in the pointed file. Index by seeds of length k all these starters.
    
    getTimeInfo().stop ("indexing");
    

    cout<<"Mapping of "<<nbReads<<" reads"<<endl;
    
    

    
    vector<ReadMapper> RMvector;
    size_t  nb_cores = getDispatcher()->getExecutionUnitsNumber ();
    for (int read_set_id=0;read_set_id<gv.number_of_read_sets;read_set_id++) {
        RMvector.push_back(ReadMapper(banks_of_queries[read_set_id],read_set_id,nb_cores));
    }
    
    
    Range<u_int64_t> range (
                            0,gv.number_of_read_sets-1
                            );
    
    // We create an iterator over our integer range.
    // Note how we use the Tool::createIterator method. According to the value of the "-verbose" argument,
    // this method will add some progression bar if needed.
    Iterator<u_int64_t>* iter = createIterator<u_int64_t> (range, "");
    LOCAL (iter);
    

    // Total number of mapped reads
    u_int64_t totalNumberOfMappedReads = 0;
    // We want to get execution time. We use the Tool::getTimeInfo() method for this.
    getTimeInfo().start ("mapping reads");
    // We iterate the range through the Dispatcher we got from our Tool parent class.
    // The dispatcher is configured with the number of cores provided by the "-nb-cores" command line argument.
    for (int read_set_id=0;read_set_id<gv.number_of_read_sets;read_set_id++)
                                                           {
                                                               index.empty_coverage();
                                                               // MAP ALL READS OF THE READ SET read_set_id
                                                               totalNumberOfMappedReads+= RMvector[read_set_id].map_all_reads_from_a_file(gv,index,read_set_id);
//                                                               // SET THE READ COHERENCY OF THIS READ SET.
                                                               RMvector[read_set_id].set_read_coherency(gv,index);
                                                           }
    
    
    

    
    getTimeInfo().stop ("mapping reads");
    
    
   
    
    
    getTimeInfo().start ("print results");
    print_results_2_paths_per_event(coherent_out, uncoherent_out, index, gv);
    getTimeInfo().stop ("print results");
    
    coherent_out.close();
    uncoherent_out.close();
    
    // We gather some statistics. Note how we use the getInfo() method from the parent class Tool
    // If the verbosity is not 0, all this information will be dumped in the console at the end
    // of the tool execution
    getInfo()->add (1, "Stats");
    getInfo()->add (2, "Total Number of Mapped reads",     "%ld",  totalNumberOfMappedReads);
    getInfo()->add (2, "Minimal coveage per read set",      sstring_cutoffs.str());
    getInfo()->add (1, "Outputs");
    getInfo()->add (2, "Number of read coherent predictions",     "%ld",  index.nb_coherent);
    getInfo()->add (2, "Number of read uncoherent predictions",     "%ld",  index.nb_uncoherent);
    
    getInfo()->add (1, getTimeInfo().getProperties("Time"));
}
