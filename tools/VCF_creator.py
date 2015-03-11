#!/bin/python
# -*- coding: utf-8 -*-
###############################################
#
#
#
import os
import sys
import subprocess
import re
import time
import getopt
from functionsVCF_creator import *
#Help
def usage():
    usage= """
    ################################
        Run VCF_creator
    ################################
    
    -h --help : print this message
    -s --sam_file : <file>.sam of the alignment
    -n --mismatch : number of differences allowed in the mapper (BWA)
    -o --output : vcf file 
    
    """
    print usage

try:
    opts, args = getopt.getopt(sys.argv[1:],"h:s:n:o:",["help","disco_file","mismatch","output="])
    if not opts:
        usage()
        sys.exit(2)
except getopt.GetoptError, e:
    print e
    usage()
    sys.exit(2)
for opt, arg in opts : 
    if opt in ("-h", "--help"):
        usage()
        sys.exit(2)
    elif opt in ("-s","--sam_file"):
        fichier = arg
        if ".sam" or ".fa" or ".fasta" in fichier:
            samfile=open(fichier,'r')
        else:
            print "...Unknown file extension for the input. Try with a <file>.sam..."
            sys.exit(2)
    elif opt in ("-n","--mismatch"):
         nbMismatchBWA= arg
    elif opt in ("-o","--output"):
        if ".vcf" in arg:
            VCF = open(arg,'w')
        else :
            print "...Unknown file extension for the output. Try with a <file>.vcf..."
            sys.exit(2)
    else:
        print("Unkwnown option {} ".format(opt))
        usage()
        sys.exit(2)


#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
###Header of the VCF file 
today=time.localtime()
date=str(today.tm_year)+str(today.tm_mon)+str(today.tm_mday)
VCF.write('##fileformat=VCFv4.1\n')
VCF.write('##filedate='+str(date)+'\n')
VCF.write('##REF=<ID=REF,Number=1,Type=String,Description="Allele of the path Disco aligned with the least mismatches ">\n')
VCF.write('##ALT=<ID=ALT,Number=1,Type=String,Description="Allele of the other path ">\n')
VCF.write('##FILTER=<ID=MULTIPLE,Number=1,Type=String,Description="Mapping type : PASS or MULTIPLE or \'.\' ">\n')
VCF.write('##INFO=<ID=Ty,Number=1,Type=Float,Description="SNP, INS, DEL or "."">\n')
VCF.write('##INFO=<ID=Rk,Number=1,Type=Float,Description="SNP rank">\n')
VCF.write('##INFO=<ID=DT,Number=1,Type=Integer,Description="Mapping distance with reference">\n')
VCF.write('##INFO=<ID=UL,Number=1,Type=Integer,Description="Lenght of the unitig left">\n')
VCF.write('##INFO=<ID=UR,Number=1,Type=Integer,Description="Lenght of the unitig right">\n')
VCF.write('##INFO=<ID=CL,Number=1,Type=Integer,Description="Lenght of the contig left">\n')
VCF.write('##INFO=<ID=CR,Number=1,Type=Integer,Description="Lenght of the contig right">\n')
VCF.write('##INFO=<ID=C,Number=1,Type=Integer,Description="Depth of each allele by samples">\n')
VCF.write('##INFO=<ID=Genome,Number=1,Type=String,Description="Allele of the reference;for indel reference is <DEL> or <INS>">\n')
VCF.write('##INFO=<ID=Sd,Number=1,Type=Integer,Description="Reverse (1) or Forward (0) Alignement">\n')
VCF.write('##FORMAT=<ID=GT,Number=1,Type=Integer,Description="Genotype">\n')
VCF.write('##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Combined depth accross samples (sum)">\n')
VCF.write('##FORMAT=<ID=PL,Number=G,Type=Float,Description="Phred-scaled Genotype Likelihoods">\n')
nbGeno=0
nbSnp=0
nbSnp,nbGeno = Comptage(fichier)
table = [0] * 10 # create a 10 cols array

##Create the header of the VCF File with all the fields + one field by genotypes/samples/individuals
if nbGeno==0: # Without genotypes
    VCF.write('#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n')
else:
    VCF.write('#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t')
    for i in range(0,int(nbGeno)):
        nomCol="G"+str(i+1)
        VCF.write(str(nomCol)+"\t")
        if i==int(nbGeno)-1:
            VCF.write(str(nomCol)+"\n")            
############################################################### 
###VCF_creator NORMAL MODE : take a samfile and create a vcf###
###############################################################
if ".sam" in fichier:
    while True:
        line1=samfile.readline()
        if not line1: break # end of file
        
        if line1.startswith('@'): continue # we do not read headers
        
        line2=samfile.readline() # read couple of lines
        
        snpUp,numSNPUp,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,valRankUp,listCoverageUp,listCUp,nb_polUp,lnUp,posDUp,ntUp,ntLow,genoUp,dicoHeaderUp=ParsingDiscoSNP(line1,0)
        snpLow,numSNPLow,unitigLeftLow,unitigRightLow,contigLeftLow,contigRightLow,valRankLow,listCoverageLow,listCLow,nb_polLow,lnLow,posDLow,ntUp,ntLow,genoLow,dicoHeaderLow=ParsingDiscoSNP(line2,0)
        
        
        
        
        if numSNPLow != numSNPUp:
            print "WARNING two consecutive lines do not store the same variant id: "
            print line1
            print line2
            sys.exit(1)
            
        #Information on coverage by dataset
        couvUp,couvLow,listCouvGeno=GetCoverage(listCUp,listCLow,listCoverageUp,listCoverageLow)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------                
        #Variables
        comptPol=0     # number of SNPs in case of close SNPs - useless for indels
        info=None      # info vcf field
        multi=None     # multi vcf field
        ok=None        # distance for which the SNP is mapped, -1 if not mapped or if multiple mapped
        dmax=False     # only one of the two paths mapped at maximal distance. 
        indel=False    # boolean to know if it is an indel
        phased=False    # am I phased?
        filterField='.' # init the vcf field filter
        posUp,posLow,snpLow,snpUp,boolMapUp,boolMapLow,boolXAUp,boolXALow = GetCouple(snpUp,snpLow) # get all the positions of mapping for one variant with the associated number of mapping errors
        seqUp=snpUp[9]   # sequences
        seqLow=snpLow[9] # sequences
        
    
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------                    
        #Validation of a couple of SNPs SEE DOC.
        NM=0
        rupture=0
        for NM in range(0,int(nbMismatchBWA)+1): 
            couple=ValidationSNP(snpLow,posLow,snpUp,posUp,NM) 
            if couple== "ok" or couple == "multiple":
                rupture=NM
                break
        if rupture==nbMismatchBWA:
            if snpLow[1]=="4":    # Sam classifies in the second filed: 0: forward mapped, 16: reverse mapped, 4: unmapped
                dmax=True
            elif snpUp[1]=="4":
                dmax=True
            else:
                dmax==False
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        #VCF champ INFO Multi
        if boolXAUp==1 and boolXALow==1:
            multi="multi"
        elif boolXAUp==0 and boolXALow==0:
            multi="none"
        elif (boolXAUp==1 and boolXALow==0) or  (boolXAUp==0 and boolXALow==1):
            multi="one"
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        #VCF champs Filter
        if couple=="ok":
            filterField="PASS"            
            ok=str(NM)
        
        elif couple == "unmapped":
            filterField="."
            ok=-1
        elif couple == "multiple":
            filterField="MULTIPLE"
            ok=-1
        else : 
            filterField="probleme...."
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        if "SNP" in snpUp[0] :
#---------------------------------------------------------------------------------------------------------------------------
            indel=False
            listPolymorphismePos=[]
            #Gets the position and the nucleotide of the variants by header parsing
            if (int(nb_polLow)>=2) or (int(nb_polUp)>=2):
                listPolymorphismePos,listnucleoUp,listnucleoLow,listPosR,listnucleoUpR,listnucleoLowR=GetPolymorphisme(dicoHeaderUp,seqUp,indel)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
            ##one SNP
            if len(listPolymorphismePos)==0:
                tp="SNP"
                table[6]=filterField
                posModif=len(snpUp[9])/2
                nucleoLow,positionSnpLow,nucleoUp,positionSnpUp,boolRefLow,boolRefUp,reverseUp,reverseLow,nucleoRefUp,nucleoRefLow = RecupPosSNP(snpUp,snpLow,posUp,posLow,nb_polUp,nb_polLow,dicoHeaderUp,indel)
                #Creation VCF
                table=fillVCFSimpleSnp(snpUp,snpLow,nucleoLow,positionSnpLow,nucleoUp,positionSnpUp,boolRefLow,boolRefUp,table,nbSnp,dmax,filterField,multi,ok,tp,phased,listCouvGeno,nucleoRefUp,nucleoRefLow,reverseUp,reverseLow,genoUp,nbGeno,couvUp,couvLow)
                printOneline(table,VCF)
                continue
    
            else: 
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
                ##Close SNPs
                indel=False
                dicoUp={}
                dicoLow={}
                posModif=None
                dicoUp,dicoLow,listPolymorphismePosUp,listPolymorphismePosLow=RecupPosSNP(snpUp,snpLow,posUp,posLow,nb_polUp,nb_polLow,dicoHeaderUp,indel)
                # this function comptutes the VCF and prints it!!
                printVCFSNPclose(dicoUp,dicoLow,table,filterField,dmax,snpUp,snpLow,listPolymorphismePosUp,listPolymorphismePosLow,listPolymorphismePos,multi,ok,couvUp,couvLow,listnucleoUp,listnucleoLow,genoUp,nbGeno,listCouvGeno,VCF) 
                continue # 
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        ##Case of INDEL                   
        if "INDEL" in snpUp[0] :
            indel=True
            table[6]=filterField
            seqInsert=0
            seqUp=snpUp[9]
            seqLow=snpLow[9]
            # To know in which sequence the insertion is and to get it
            #Reverse the sequence to get the good mapped insert if it needs to
            seqUp,seqLow=GetSequence(snpUp,snpLow)
            if len(seqUp)<len(seqLow):
                seq=seqLow
            else:
                seq=seqUp
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
            #Get from the dicoHeader[key]=[posD,ind,amb]: Position of the insertion ; the insertion with the nucleotide just before ; the nucleotide just before ; the possible ambiguity for the position of the insertion 
            listPos,listPosR,insert,ntStart,ambiguity=GetPolymorphisme(dicoHeaderUp,seq,indel)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
            #Parsing of the discosnp Header
            snpUp,numSNPUp,unitigLeftUP,unitigRightUp,contigLeftUp,contigRightUp,valRankUp,listCoverageUp,listCUp,nb_polUp,lnUp,posDUp,ntUp,ntLow,genoUp,dicoHeaderUp=ParsingDiscoSNP(snpUp,0)
            snpLow,numSNPLow,unitigLeftLow,unitigRightLow,contigLeftLow,contigRightLow,valRankLow,listCoverageLow,listCLow,nb_polLow,lnLow,posDLow,ntUp,ntLow,genoLow,dicoHeaderLow=ParsingDiscoSNP(snpLow,0)
            nucleoLow,positionSnpLow,nucleoUp,positionSnpUp,boolRefLow,boolRefUp,reverseUp,reverseLow,nucleoRefUp,nucleoRefLow= RecupPosSNP(snpUp,snpLow,posUp,posLow,nb_polUp,nb_polLow,dicoHeaderUp,indel)
            #Check the strand (forward or reverse) to have the right sequence of insert
            if boolRefUp==True and reverseUp==-1:
                insert=ReverseSeq(insert)
                ntStart=ReverseComplement(ntStart)
            elif boolRefLow==True and reverseLow==-1:
                insert=ReverseSeq(insert)
                ntStart=ReverseComplement(ntStart)
            #Check if the insert correpond to the upper path or to the lower path
            if len(seqUp)<len(seqLow):
                nucleoLow=insert
                nucleoUp=ntStart
            else:
                nucleoUp=insert
                nucleoLow=ntStart
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
            ## Fill the VCF if the upper path is considered as the reference
            if boolRefUp==True:
                if len(nucleoUp)==len(insert):
                    nucleoRefUp="."
                    tp="INS"
                else:
                    nucleoRefUp="."
                    tp="DEL"
                table=FillVCF(table,numSNPUp,snpUp[2],int(positionSnpUp)-1,nucleoUp,nucleoLow,snpUp[10],filterField,tp,valRankUp,multi,ok,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,couvUp,nucleoRefUp,reverseUp,genoUp,nbGeno,phased,listCouvGeno,boolRefLow)
            ## Fill the VCF if the lower path is considered as the reference
            elif boolRefLow==True:
                if len(nucleoLow)==len(insert):
                    nucleoRefLow="."
                    tp="INS"
                else:
                    nucleoRefLow="."
                    tp="DEL"
                table=FillVCF(table,numSNPLow,snpLow[2],int(positionSnpLow)-1,nucleoLow,nucleoUp,snpLow[10],filterField,tp,valRankLow,multi,ok,unitigLeftLow,unitigRightLow,contigLeftLow,contigRightLow,couvLow,nucleoRefLow,reverseLow,genoLow,nbGeno,phased,listCouvGeno,boolRefLow)
            printOneline(table,VCF)
            
#---------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------- 
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
##################################################################### 
###VCF_creator GHOST MODE : take a fasta in input and create a vcf###
#####################################################################   
else:
    while True:
        line1=samfile.readline()
        if not line1: break # end of file
        seq1=samfile.readline() # read the seq associate to the SNP
        line2=samfile.readline() # read a couple of line
        seq2=samfile.readline()
        line1=line1.rstrip('\n')
        line1=line1.strip('>')
        line2=line2.rstrip('\n')
        line2=line2.strip('>')
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------        
        #Variables
        comptPol=0     # number of SNPs in case of close SNPs - useless for indels
        
        snpUp,numSNPUp,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,valRankUp,listCoverageUp,listCUp,nb_polUp,lnUp,posDUp,ntUp,ntLow,genoUp,dicoHeaderUp=ParsingDiscoSNP(line1,0)
        snpLow,numSNPLow,unitigLeftLow,unitigRightLow,contigLeftLow,contigRightLow,valRankLow,listCoverageLow,listCLow,nb_polLow,lnLow,posDLow,ntUp,ntLow,genoLow,dicoHeaderLow=ParsingDiscoSNP(line2,0)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------        
        if numSNPLow != numSNPUp:
            print "WARNING two consecutive lines do not store the same variant id: "
            print line1
            print line2
            sys.exit(1)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------            
        #Information on coverage by dataset
        couvUp,couvLow,listCouvGeno=GetCoverage(listCUp,listCLow,listCoverageUp,listCoverageLow)
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        ##one SNP
        if "SNP" in line1:
            tp="SNP"
            indel=False
            listPolymorphismePos=[]
            #Gets the position and the nucleotide of the variants by header parsing
            if (int(nb_polLow)>=2) or (int(nb_polUp)>=2):
                listPolymorphismePos,listnucleoUp,listnucleoLow,listPosR,listnucleoUpR,listnucleoLowR=GetPolymorphisme(dicoHeaderUp,seq1,indel)
	#dicoHeader[key]=[posD,ntUp,ntLow]
	    if len(listPolymorphismePos)==0:
                ntLow=dicoHeaderUp["P_1"][2]
                ntUp=dicoHeaderUp["P_1"][1]
                phased=False
                PrintVCFGhost(table,numSNPUp,tp,valRankUp,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,couvUp,ntUp,ntLow,genoUp,nbGeno,phased,listCouvGeno,VCF)
                continue
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
            ##Close SNPs
	    else:
                phased=True
                for comptPol in range(0,len(listPolymorphismePos)):
                        key="P_"+str(comptPol+1)
                        ntLow=dicoHeaderUp[key][2]
                        ntUp=dicoHeaderUp[key][1]
                        PrintVCFGhost(table,numSNPUp,tp,valRankUp,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,couvUp,ntUp,ntLow,genoUp,nbGeno,phased,listCouvGeno,VCF)
                continue
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
        ##Case of INDEL
        elif "INDEL" in line1:
            indel=True
            phased=False
            if len(seq1)<len(seq2):
                seq=seq1
            else:
                seq=seq2
            listPos,listPosR,insert,ntStart,ambiguity=GetPolymorphisme(dicoHeaderUp,seq,indel)                
            if seq==seq1:
                ntLow=ntStart
                ntUp=insert
            else:
                ntUp=ntStart
                ntLow=insert
            PrintVCFGhost(table,numSNPUp,tp,valRankUp,unitigLeftUp,unitigRightUp,contigLeftUp,contigRightUp,couvUp,ntUp,ntLow,genoUp,nbGeno,phased,listCouvGeno,VCF)
            continue     
        	
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------

VCF.close()
samfile.close()



