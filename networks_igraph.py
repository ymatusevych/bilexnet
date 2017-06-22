from igraph import *
import csv
import os
from collections import Counter
import utils
import pandas
import ml_metrics as metrics
import random
from scipy.stats import ttest_rel
import numpy as np
import pickle
import itertools
import copy

np.random.seed(12345678)

mapping = {'E': ":EN", 'D': ":NL"}
noise_list = ["x", "", None]
alpha = 1

def plot_subgraph(plot_graph, w, depth, name):
    # Traverses the graph for a given word and plots the resulting subgraph into a file. Needs to be tested.
    starting_vertex = {plot_graph.vs.find(name=w): 1}
    G_sub = Graph(directed=True)
    G_sub.add_vertices(w)
    G_sub.vs["name"] = [w]
    responses, G_sub = spread_activation_plot(plot_graph, starting_vertex, G_sub, depth)
    visual_style = {}
    visual_style["vertex_size"] = 10
    visual_style["vertex_label"] = G_sub.vs["name"]
    visual_style["edge_width"] = G_sub.es['weight']
    visual_style["bbox"] = (1000, 1000)
    visual_style["margin"] = 20
    plot(G_sub, w + "_"+ name + ".svg", **visual_style)


def invert_dict(d):
    # Inverts a dictionary of {string:list} pairs.
    newdict = {}
    for k in d:
        for v in d[k]:
            newdict.setdefault(v, []).append(k)
    return newdict

def filter_test_list(G, test_list):
    # Filters out test words that are absent in the big graph.
    test_list_cleaned = [w for w in test_list if w in G.vs['name']]
    test_list_cleaned = [w for w in test_list_cleaned if G.incident(w)]
    return(test_list_cleaned)

def construct_bilingual_graph(enG, nlG, en_nl_dic, TE_weight):
    # Constructs a bilingual graph with translation edges and pickles it. If a pickled file found, loads it instead.
    fn = "./biling_graph/biling_pickled_weight_" + str(TE_weight)
    if os.path.isfile(fn):
        biling = read(fn, format="pickle")
    else:
        en_nl_tuples = [(k,v,TE_weight) for k,vs in en_nl_dic.items() for v in vs]
        TE_edges = [t for t in en_nl_tuples if t[0] in enG.vs['name'] and t[1] in nlG.vs['name']]
        TE_edges_reversed = [(t[1],t[0],t[2]) for t in TE_edges]
        TE_edges.extend(TE_edges_reversed)

        df = pandas.read_csv("./Dutch/associationDataLemmas.csv", sep=";")
        edges = Counter()
        for i in range(1, 4):
            edges.update(zip(df['cue'], df['asso' + str(i)]))
        weighted_edges = [(e[0][0] + ":NL", e[0][1] + ":NL", e[1]) for e in edges.items() if e[0][1] not in noise_list]

        weighted_edges.extend([(enG.vs['name'][e.tuple[0]], enG.vs['name'][e.tuple[1]], e.attributes()['weight']) for e in enG.es if enG.vs['name'][e.tuple[1]] not in noise_list])
        weighted_edges.extend(TE_edges)

        biling = Graph.TupleList(edges=weighted_edges, edge_attrs="weight", directed=True)
        biling.write_pickle("./biling_graph/biling_pickled_weight_"+str(TE_weight))
    return(biling)


def preprocess_word(w):
    # An auxiliary function to clean test files.
    if w[0:2] == "vk":
        w = w[2:]
    if w=="geen":
        return None
    if "(" in w:
        w = w[:w.index("(")]
    return(w)

def read_test_file(fn):
    # An auxiliary function that reads a single test file.
    conditions = fn.split("/")[-1].split('.')[0].split('-')
    cue_langs = [c[0] for c in conditions]
    target_langs = [c[1] for c in conditions]
    n_conds = len(conditions)
    resp_dict = {}
    with open(fn) as f:
        test_reader = csv.reader(f, delimiter=",")
        next(test_reader)
        for row in test_reader:
            cue = row[1]
            responses_mixed = row[3:]
            for cond_idx in range(n_conds):
                cue_lang = cue_langs[cond_idx]
                target_lang = target_langs[cond_idx]
                if cue_lang not in resp_dict:
                    resp_dict[cue_lang] = {}
                if target_lang not in resp_dict[cue_lang]:
                    resp_dict[cue_lang][target_lang] = []
                target_responses = [(cue+mapping[cue_lang], preprocess_word(responses_mixed[r_idx])+mapping[target_lang]) for r_idx in range(len(responses_mixed))
                                    if r_idx%n_conds==cond_idx and preprocess_word(responses_mixed[r_idx])!=None]
                resp_dict[cue_lang][target_lang].extend(target_responses)
    return(resp_dict)

def read_test_data():
    # Reads test data of Van Hell & De Groot (1998). CSV format needed.

    DD_DE_DD_test_dict = read_test_file("./vanhell/DD1-DE2-DD3.csv")
    DE_DD_test_dict = read_test_file("./vanhell/DE1-DD2.csv")
    ED_EE_test_dict = read_test_file("./vanhell/ED1-EE2.csv")
    EE_ED_EE_test_dict = read_test_file("./vanhell/EE1-ED2-EE3.csv")

    DD_test_lists = [DD_DE_DD_test_dict['D']['D'],
                     DE_DD_test_dict['D']['D']]
    gold_dict = {'DD':{},'DE':{},'EE':{},'ED':{}}
    for tl in DD_test_lists:
        for (c, r), f in Counter(tl).items():
            if r != "":
                if c not in gold_dict['DD']: gold_dict['DD'][c] = []
                gold_dict['DD'][c].append((r,f))

    EE_test_lists = [EE_ED_EE_test_dict['E']['E'],
                     ED_EE_test_dict['E']['E']]
    for tl in EE_test_lists:
        for (c, r), f in Counter(tl).items():
            if r != "":
                if c not in gold_dict['EE']: gold_dict['EE'][c] = []
                gold_dict['EE'][c].append((r, f))

    DE_test_lists = [DD_DE_DD_test_dict['D']['E'],
                     DE_DD_test_dict['D']['E']]
    for tl in DE_test_lists:
        for (c, r), f in Counter(tl).items():
            if r != "":
                if c not in gold_dict['DE']: gold_dict['DE'][c] = []
                gold_dict['DE'][c].append((r, f))

    ED_test_lists = [EE_ED_EE_test_dict['E']['D'],
                     ED_EE_test_dict['E']['D']]
    for tl in ED_test_lists:
        for (c, r), f in Counter(tl).items():
            if r != "":
                if c not in gold_dict['ED']: gold_dict['ED'][c] = []
                gold_dict['ED'][c].append((r, f))

    return(gold_dict)


def read_dict(fn):
    # Reads an English-Dutch dictionary from CSV.
    dic = {}
    with open(fn) as fin:
        reader = csv.reader(fin, skipinitialspace=True, quotechar=None)
        next(reader)
        for row in reader:
            source = row[0]+":EN"
            transl = row[1]+":NL"
            if source not in dic: dic[source] = []
            dic[source].append(transl)
    return (dic)

def construct_igraph(fn):
    # Constructs the big (Dutch) graph from CSV.
    df = pandas.read_csv(fn, sep=";")
    edges = Counter()
    for i in range(1,4):
        edges.update(zip(df['cue'], df['asso'+str(i)]))
    weighted_edges = [(e[0][0]+":NL",e[0][1]+":NL",e[1]) for e in edges.items() if e[0][1] not in noise_list]
    G = Graph.TupleList(edges=weighted_edges, edge_attrs="weight", directed=True)
    return G

def clean_igraph(D):
    # Removes noisy vertices from the graph.
    to_delete_ids = []
    for vx in D.vs:
        if vx["id"] in noise_list:
            to_delete_ids.append(vx.index)
        else:
            vx["name"] = vx["id"] + ":EN"
    D.delete_vertices(to_delete_ids)
    return(D)


def get_graph(fn, language):
    # Constructs a graph, either English or Dutch, from a file.
    if os.path.isfile(fn+"_pickled"):
        D = read(fn+"_pickled", format="pickle")
    else:
        if language=="nl":
            D = construct_igraph(fn)
        elif language=="en":
            D = read(fn, format="pajek")
            D = clean_igraph(D)
        D.write_pickle(fn+"_pickled")
    return D

def spread_activation(G, responses, depth):
    # Main function that spreads the activation starting from the given node(s) and returns a dictionary of responses with their (non-normalized) likelihoods.
    if depth == 0:
        return({})
    else:
        responses_current_level = dict()
        for vertex in sorted(responses):
            weight = responses[vertex]
            new = {}
            for e in G.incident(vertex):
                if random.random() < alpha:
                    new[G.vs[G.es[e].tuple[1]]] = G.es[e]["weight"]
            total = sum(new.values())
            if total == 0:
                responses_single_word = {}
            else:
                responses_single_word = {k:v/total*weight*alpha for k,v in new.items()}
            responses_current_level = dict(sum((Counter(x) for x in [responses_current_level, responses_single_word]), Counter()))
        if not responses_current_level:
            return({})
        else:
            responses_next_level = spread_activation(G, responses_current_level, depth-1)
        final_vertices = dict(sum((Counter(x) for x in [responses_current_level, responses_next_level]), Counter()))
        return(final_vertices)

def spread_activation_plot(G, responses, G_sub, depth):
    # An auxiliary function that spreads activation for plotting a subgraph.
    if depth == 0:
        return({}, G_sub)
    else:
        responses_current_level = dict()
        for vertex in sorted(responses):
            weight = responses[vertex]
            new = {}
            for e in G.incident(vertex):
                if random.random() < alpha:
                    new[G.vs[G.es[e].tuple[1]]] = G.es[e]["weight"]
            total = sum(new.values())
            if total == 0:
                responses_single_word = {}
            else:
                responses_single_word = {k:v/total*weight*alpha for k,v in new.items()}
                for resp,wei in new.items():
                    if resp not in G_sub.vs['name']:
                        G_sub.add_vertex(name=resp['name'])
                    e = G_sub.get_eid(G_sub.vs.find(name=vertex['name']), G_sub.vs.find(name=resp['name']), directed=True, error=False)
                    if e != -1:
                        G_sub.es[e]['weight'] += wei
                    else:
                        G_sub.add_edge(vertex['name'],resp['name'],weight=wei)
            responses_current_level = dict(sum((Counter(x) for x in [responses_current_level, responses_single_word]), Counter()))
        if not responses_current_level:
            return({}, G_sub)
        else:
            responses_next_level, G_sub = spread_activation_plot(G, responses_current_level, G_sub, depth-1)
        final_vertices = dict(sum((Counter(x) for x in [responses_current_level, responses_next_level]), Counter()))
        return(final_vertices, G_sub)

def normalize_dict(d, target=1.0):
    #Normalizes dictionary values to 1.
    raw = sum(d.values())
    if raw == 0: return{}
    factor = target/raw
    return {key:value*factor for key,value in d.items()}

def test_network(D, test_list, depth, direction, translation_dict=None, gold_full=None, verbose=True):
    # Tests the big network on a test list with words, using any language direction from Van Hell and De Groot (1998):
    # 'DD': Dutch stimulus, Dutch responses
    # 'DE': Dutch stimulus, English responses
    # 'ED': English stimulus, Dutch responses
    # 'EE': English stimulus, English responses
    # Returns three lists, one for each metrics:
    # - TVD (total variation distance)
    # - RBD (rank-biased distance)
    # - APK (average precision at k)
    # The length of each list equals to the length of the test word list.
    # Also prints responses if verbose is True.
    gold = gold_full[direction]
    stimulus_lang = mapping[direction[0]]
    response_lang = mapping[direction[1]]
    tvds = []
    rbds = []
    apks = []
    tvd = 0
    rbd = 0
    apk = 0
    for w in test_list:
        gold_local = dict(gold[w])
        gold_clean = {k:v for k,v in gold_local.items() if gold_local[k] > 1}
        d_gold = normalize_dict(gold_clean)
        l_gold = sorted(d_gold.items(), key=lambda x: (-x[1],x[0]))
        k_gold = [pair[0] for pair in l_gold]
        starting_vertex = {D.vs.find(name=w): 1}
        responses = {vx['name']: wgt for vx, wgt in spread_activation(D, starting_vertex, depth).items()}
        if w in responses:
            del responses[w]
        if stimulus_lang != response_lang:
            if w in translation_dict:
                for trnsl in translation_dict[w]:
                    if trnsl in responses:
                        del responses[trnsl]
        responses_clean = {r: p for r, p in responses.items() if r[-3:]==response_lang}
        d_resp = normalize_dict(responses_clean)
        l_resp = sorted(d_resp.items(), key=lambda x: (-x[1],x[0]))
        k_resp = [pair[0] for pair in l_resp]
        dm_resp = normalize_dict({k:v for k,v in d_resp.items() if k in k_resp[:len(k_gold)]})
        if verbose:
            print("\tCUE:",w)
            if gold:
                print("\t\tGOLD")
                for k, v in l_gold[:10]:
                    print("\t\t\t%s\t\t%.3f" % (k, v))
            print("\t\tMAX DEPTH:", depth)
            for k,v in l_resp[:10]:
                print("\t\t\t%s\t\t%.10f" % (k, v))
        if gold:
            apk_k = len(gold_clean)
            tvd_w = 0.5 * sum(abs((d_gold.get(resp) or 0) - (dm_resp.get(resp) or 0)) for resp in set(d_gold) | set(dm_resp))
            rbd_w = utils.get_rbd(k_gold, k_resp)
            apk_w = 1-metrics.apk(k_gold, k_resp, apk_k)
            tvd += tvd_w
            rbd += rbd_w
            apk += apk_w
            #print("\t\tTVD:", tvd_w)
            #print("\t\tRBD:", rbd_w)
            #print("\t\tAPK:", apk_w)
            tvds.append(tvd_w)
            rbds.append(rbd_w)
            apks.append(apk_w)
    if gold:
        tvd /= len(test_list)
        rbd /= len(test_list)
        apk /= len(test_list)
        print("\tTotal variation distance :", tvd)
        print("\tRank-biased distance :", rbd)
        print("\tAverage precision (distance) :", apk)
    return (tvds, rbds, apks)


if __name__ == "__main__":

    en_nl_dic = read_dict("./dict/dictionary.csv")
    nl_en_dic = invert_dict(en_nl_dic)

    en = get_graph(fn="./EAT/shrunkEAT.net", language="en")
    nl = get_graph(fn="./Dutch/shrunkdutch2.csv", language="nl")

    gold_dict = read_test_data()

    test_list_DD = filter_test_list(nl, sorted(gold_dict['DD'].keys()))
    test_list_EE = filter_test_list(en, sorted(gold_dict['EE'].keys()))
    test_list_DE = filter_test_list(nl, sorted(gold_dict['DE'].keys()))
    test_list_ED = filter_test_list(en, sorted(gold_dict['ED'].keys()))

    #test = ['DD', 'EE', 'DE']
    test = ['EE']

    depth_baseline = 1
    depth = 2
    for TE_weight in [1]:

        biling = construct_bilingual_graph(en, nl, en_nl_dic, TE_weight)

        if 'DD' in test:
            print("NET:%s, DEPTH:%i, TE:%i" % ("nl", depth_baseline, TE_weight))
            tvd_base, rbd_base, apk_base = test_network(nl, test_list_DD, depth, 'DD', gold_full=gold_dict, verbose=False)
            print("NET:%s, DEPTH:%i, TE:%i" % ("bi", depth, TE_weight))
            tvd_m, rbd_m, apk_m = test_network(biling, test_list_DD, depth, 'DD', gold_full=gold_dict, verbose=False)
            print("TVD t-test: T=%.2f, p=%.3f" % (ttest_rel(tvd_base, tvd_m)[0], ttest_rel(tvd_base, tvd_m)[1]))
            print("RBD t-test: T=%.2f, p=%.3f" % (ttest_rel(rbd_base, rbd_m)[0], ttest_rel(rbd_base, rbd_m)[1]))
            print("APK t-test: T=%.2f, p=%.3f" % (ttest_rel(apk_base, apk_m)[0], ttest_rel(apk_base, apk_m)[1]))

        if 'EE' in test:
            print("NET:%s, DEPTH:%i, TE:%i" % ("en", depth_baseline, TE_weight))
            tvd_base, rbd_base, apk_base = test_network(en, test_list_EE, depth_baseline, 'EE', gold_full=gold_dict, verbose=True)
            print("NET:%s, DEPTH:%i, TE:%i" % ("bi", depth, TE_weight))
            tvd_m, rbd_m, apk_m = test_network(biling, test_list_EE, depth, 'EE', gold_full=gold_dict, verbose=True)
            #tvd_m, rbd_m, apk_m = test_network(en, test_list_EE, depth, 'EE', gold_full=gold_dict, verbose=True)
            print("TVD t-test: T=%.2f, p=%.3f" % (ttest_rel(tvd_base, tvd_m)[0], ttest_rel(tvd_base, tvd_m)[1]))
            print("RBD t-test: T=%.2f, p=%.3f" % (ttest_rel(rbd_base, rbd_m)[0], ttest_rel(rbd_base, rbd_m)[1]))
            print("APK t-test: T=%.2f, p=%.3f" % (ttest_rel(apk_base, apk_m)[0], ttest_rel(apk_base, apk_m)[1]))

        if 'DE' in test:
            print("NET:%s, DEPTH:%i, TE:%i" % ("bi", depth, TE_weight))
            tvd, rbd, apk = test_network(biling, test_list_DE, depth, 'DE', nl_en_dic, gold_full=gold_dict, verbose=False)

        if 'ED' in test:
            print("NET:%s, DEPTH:%i, TE:%i" % ("bi", depth, TE_weight))
            tvd, rbd, apk = test_network(biling, test_list_ED, depth, 'ED', en_nl_dic, gold_full=gold_dict, verbose=False)

        # plot_list = ["captain:EN"]
        # for w in plot_list:
        #     plot_subgraph(biling,w,2, "biling")

