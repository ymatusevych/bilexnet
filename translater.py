import os
import re
from dutch import Graphnx

def dict_parser():
    '''
    returns a dictionary of Dutch-->English
    
    every Dutch word has a corresponding list of English words that it is translated to.
    
    The direct variable is the location of the .tei file
    
    '''
    
    direct = '/Users/amirardalankalantaridehgahi/Desktop/school/stevensonRA/dict'  #change it
    fil = open(os.path.join(direct, "nld-eng.tei"), "r")

    tei = fil.readlines()

    DICT = {}

    new_entry = False
    entrant = None
    count = 0
    for line in tei:
        if line.strip() == "<entry>":
            new_entry = True
            count = count + 1
        
        if line.strip() =="</entry>":
            new_entry = False
            entrant = None
            
        if new_entry == True:
            
            if line.strip()[:6] == "<orth>":
                line = re.sub(r'<orth>', '',line.strip()) 
                line = re.sub(r'</orth>', '',line)
                DICT[line] = []
                entrant = line
                print(entrant,'  entry')
                
            if line.strip()[:7] == "<quote>":
                line = re.sub(r'<quote>', '',line.strip()) 
                line = re.sub(r'</quote>', '',line)
                
                DICT[entrant].append(line)
                print(line,'  trans')
        
        #if count == 20:
        #    break
    print(count, '  count')
    return DICT


if __name__ == "__main__":
    dikt = dict_parser()
    raw_input()
    G = Graphnx()
    nodes = G.nodes()
    
    hits = 0
    miss = 0
    
    for n in nodes:
        if n in dikt:
            hits = hits + 1
            
        else:
            print(n, '  MISSSEEEEDDDDDDDD')
            miss = miss + 1
            
    print(hits , '  hits')
    print(miss , '   misses')