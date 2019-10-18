#!/bin/sh

# REQUIRES:
## Python 3
## short_read_connector: installed and compiled: https://github.com/GATB/short_read_connector
# echo "WARNING: short_read_connector must have been compiled"


function help {
echo "====================================================="
echo "Filtering, clustering per locus and vcf formatting of $rawdiscofile"
echo "====================================================="
echo "this script manages bubble clustering from a discofile.fa file, and the integration of cluster informations in a vcf file"
echo " 1/ Remove variants with more than 95% missing genotypes and low rank (<0.4)"
echo " 2/ Cluster variants per locus"
echo " 3/ Format the variants in a vcf file with cluster information"
echo "Usage: ./discoRAD_clustering.sh -f discofile -s SRC_directory/ -o output_file.vcf"
# echo "nb: all options are MANDATORY\n"
echo "OPTIONS:"
echo "\t -f: DiscoSnp fasta output containing coherent predictions"
echo "\t -s: Path to Short Read Connector"
echo "\t -o: output file path (vcf)"
echo "\t -w: Wraith mode: only show all discoSnpRad commands without running them"
}

wraith="false"
# if [ "$#" -lt 7 ]; then
# help
# exit
# fi

while getopts "f:s:o:hw" opt; do
    case $opt in
        f)
        rawdiscofile=$OPTARG
        ;;

        s)
        short_read_connector_directory=$OPTARG
        ;;

        o)
        output_file=$OPTARG
        ;;

        w)
        wraith="true"
        ;;

        h)
        help
        exit
        ;;
    esac
done

if [[ -z "${rawdiscofile}" ]]; then
    echo "-f is mandatory" >&2
    exit
fi
if [[ -z "${short_read_connector_directory}" ]]; then
    echo "-s is mandatory" >&2
    exit
fi
if [[ -z "${output_file}" ]]; then
    echo "-o is mandatory" >&2
    exit
fi
# Detect the directory path
EDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BINDIR=$EDIR"/../../build/bin"
rawdiscofile_base=$( basename  "${rawdiscofile}" .fa)

#################### PARAMETERS VALUES #######################

#Get k value (for clustering purpose)
originalk=$( echo $rawdiscofile | awk -F k_ '{ print $2 }' | cut -d "_" -f 1)
usedk=$((originalk-1))

## Short Read Connector is limited to kmers of size at most 31 (u_int64). 
if [ ${usedk} -gt 31 ]
then
usedk=31
fi

# rank filter parameter
min_rank=0.4

# max cluster size parameter
max_cluster_size=150

percent_missing=0.95

echo "############################################################"
echo "######### MISSING DATA AND LOW RANK FILTERING  #############"
echo "############################################################"

echo "#Filtering variants with more than ${min_rank} missing data and rank<${min_rank} ..."

disco_filtered=${rawdiscofile_base}_filtered
cmdFilter="python3 ${EDIR}/fasta_and_cluster_to_filtered_vcf.py -i ${rawdiscofile} -f -o ${disco_filtered}.fa -m ${percent_missing} -r ${min_rank} 2>&1 "
echo $cmdFilter
if [[ "$wraith" == "false" ]]; then
    eval $cmdFilter
    

    if [ ! -s ${disco_filtered}.fa ]; then
        echo "No variant pass the filters, exit"
        exit 0
    fi
fi

######################### Clustering ###########################

echo "############################################################"
echo "###################### CLUSTERING ##########################"
echo "############################################################"

echo "#Clustering variants (sharing at least a ${usedk}-mers)..."

# Simplify headers (for dsk purposes)

disco_simpler=${disco_filtered}_simpler
cmdCat="cat ${disco_filtered}.fa | cut -d \"|\" -f 1 | sed -e \"s/^ *//g\""
echo $cmdCat "> ${disco_simpler}.fa"
if [[ "$wraith" == "false" ]]; then
    eval $cmdCat > ${disco_simpler}.fa
fi

 
#cat ${disco_filtered}.fa | cut -d "|" -f 1 | sed -e "s/^ *//g" > ${disco_simpler}.fa
cmdLs="ls ${disco_simpler}.fa"
echo $cmdLs "> ${disco_simpler}.fof"
if [[ "$wraith" == "false" ]]; then
    eval $cmdLs > ${disco_simpler}.fof
fi
#ls ${disco_simpler}.fa > ${disco_simpler}.fof

# Compute sequence similarities
cmdSRC="${short_read_connector_directory}/short_read_connector.sh -b ${disco_simpler}.fa -q ${disco_simpler}.fof -s 0 -k ${usedk} -a 1 -l -p ${disco_simpler}  1>&2 "
echo $cmdSRC
if [[ "$wraith" == "false" ]]; then
    eval $cmdSRC
fi

if [ $? -ne 0 ]
then
    echo "there was a problem with Short Read Connector, exit"
    exit 1
fi

# Format one line per edge
cmd="python3 ${EDIR}/from_SRC_to_edges.py ${disco_simpler}.txt"
echo $cmd "> ${disco_simpler}_edges.txt"
if [[ "$wraith" == "false" ]]; then
    eval $cmd "> ${disco_simpler}_edges.txt"
fi

# Compute the clustering
cmdqhc="${BINDIR}/quick_hierarchical_clustering ${disco_simpler}_edges.txt"
echo $cmdqhc " > ${disco_simpler}.cluster"
if [[ "$wraith" == "false" ]]; then
    eval $cmdqhc "> ${disco_simpler}.cluster"
fi

if [ $? -ne 0 ]
then
    echo "there was a problem with quick_hierarchical_clustering, exit"
    exit 1
fi

######################### VCF generation with cluster information FROM ORIGINAL FASTA ###########################

echo "############################################################"
echo "###################### OUTPUT VCF ##########################"
echo "############################################################"

cmdVCF="python3 ${EDIR}/fasta_and_cluster_to_filtered_vcf.py -i ${disco_filtered}.fa -o ${output_file} -c ${disco_simpler}.cluster -s ${max_cluster_size} 2>&1 "
echo $cmdVCF
if [[ "$wraith" == "false" ]]; then
    eval $cmdVCF
fi

if [ $? -ne 0 ]
then
    echo "there was a problem with vcf creation, exit"
    exit 1
fi

echo "#######################################################################"
echo "#########################  CLEANING  ##################################"
echo "#######################################################################"


rm -f ${disco_simpler}*
rm -f ${disco_filtered}.fa



echo "============================"
echo " DISCORAD clustering DONE "
echo "============================"
echo " Results in ${output_file}"
