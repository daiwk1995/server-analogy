"""
analogy.py

module for making analogies between standard graph structures


"""

import numpy as np
from utils import permute_rtype_vector, cosine_similarity, euclidean_distance
import math

from pprint import pprint

class AnalogyException(Exception):
    pass

def make_analogy(src_concept, src_domain, target_concept, target_domain,
                 rmax=1, vmax=1, cluster_mode=0):
    '''Makes the best analogy between two concepts in two domains

    src_domain is the KNOWN domain
    target_domain is the NOVEL domain

    returns the best analogy that can be made between the two concepts

    In cluster mode, the analogy will be computed using a single example of
    each relationship type, weighted appropriately. This is useful for nodes
    with a very large number of homogeneous connections as it severely cuts
    down on the computation time.

    0 = default (no clustering)
    1 = source domain clustering only
    2 = target domain clustering only
    3 = both domains will be clustered

    raises an AnalogyException if concept does not exist in domain
    '''

    # ensure features exist
    if not src_concept in src_domain.nodes:
        raise AnalogyException("'%s' not in source domain" % src_concept)

    if not target_concept in target_domain.nodes:
        raise AnalogyException("'%s' not in target domain" % target_concept)

    cnode = src_domain.nodes[src_concept]
    tnode = target_domain.nodes[target_concept]

    nc1 = cnode.get_rtype_ratios()
    nc2 = tnode.get_rtype_ratios()

    tv1 = sum([len(x) for x in src_domain.usage_map.values()])
    tv2 = sum([len(x) for x in target_domain.usage_map.values()])

    tscore = rmax + vmax

    def get_confidence(r1,r2):
        #get the relative confidence between two relationship types

        ##confidence based on total knowledge
        c1 = len(src_domain.usage_map[r1])
        c2 = len(target_domain.usage_map[r2])

        ratio1 = c1/tv1
        ratio2 = c2/tv2

        diff1 = (ratio1 - ratio2)**2

        #confidence based on relative usage
        diff2 = (nc1[r1] - nc2[r2])**2

        return 1 - (diff1+diff2)/2

    def get_hypotheses():

        hypotheses = []

        if cluster_mode == 0: #no cluster
            svdi = cnode.get_vec_dict(src_domain,False).items()
            tvdi = tnode.get_vec_dict(target_domain,False).items()
        elif cluster_mode == 1: #src only cluster
            svdi = cnode.get_vec_dict(src_domain,True).items()
            tvdi = tnode.get_vec_dict(target_domain,False).items()
        elif cluster_mode == 2: #trg only cluster
            svdi = cnode.get_vec_dict(src_domain,False).items()
            tvdi = tnode.get_vec_dict(target_domain,True).items()
        else: #both cluster
            svdi = cnode.get_vec_dict(src_domain,True).items()
            tvdi = tnode.get_vec_dict(target_domain,True).items()

        # for each pair in target in/out
        for (r2, d2, v2), (vdiff2, rdiff2) in tvdi:
            #compare with each pair in source in/out
            for (r1, d1, v1), (vdiff1, rdiff1) in svdi:

                if cluster_mode == 0:
                    #compute relative rtype score
                    rscore = cosine_similarity(rdiff1, rdiff2)

                    #compute relative node score
                    vscore = cosine_similarity(vdiff1, vdiff2)

                elif cluster_mode == 1:
                    #compute relative rtype score
                    rscore = cosine_similarity(rdiff1*nc1[r1], rdiff2)

                    #compute relative node score
                    vscore = cosine_similarity(vdiff1*nc1[r1], vdiff2)

                elif cluster_mode == 2:
                    #compute relative rtype score
                    rscore = cosine_similarity(rdiff1, rdiff2*nc2[r2])

                    #compute relative node score
                    vscore = cosine_similarity(vdiff1, vdiff2*nc2[r2])

                else:
                    #compute relative rtype score
                    rscore = cosine_similarity(rdiff1*nc1[r1], rdiff2*nc2[r2])

                    #compute relative node score
                    vscore = cosine_similarity(vdiff1*nc1[r1], vdiff2*nc2[r2])

                #adjust by tfidf
                try:
                    rscore *= src_domain.tfidf[d1][r1] * target_domain.tfidf[d2][r2]
                except KeyError:#ignore clusters for now
                    pass

                #adjust rtype score by relative confidence
                rscore *= get_confidence(r1,r2)

                #skew score
                rscore = math.tanh(2*math.e*rscore - math.e)
                #vscore = math.tanh(2*math.e*vscore - math.e)

                #compute final score
                actual_score = (rscore*rmax + vscore*vmax)/tscore

                hypotheses.append((actual_score, r1, d1, r2, d2, v1, v2))

        hypotheses.sort(reverse=True)
        #print the data to analyze
        '''count=0
        total=0
        maxscore=0.0
        b=""
        with open("document","w+") as f:
            for score, r1, src, r2, target, v1, v2 in hypotheses:
                a=r2
                if r1=="music subgenre":
                    if v1:
                        if v2:
                            #f.write(str(r1)+"+"+str(r2)+"+"+str(score)+"\n")
                            if(maxscore<score):
                                maxscore=score
                            total = total+1
                            if b==a or b=="":
                                b=a
                                count = count+1
                            else:
                                f.write(str(r1)+"+"+str(b)+"+"+str(maxscore)+"+"+str(count)+"\n")
                                maxscore=score
                                b=a
                                count=1
            f.write(str(total))'''
        return hypotheses

    rassert = {}
    hmap = {}
    best = {}
    rating = 0
    total_rating = 0

    #use dict views to avoid copying
    hkeys = hmap.keys()
    hvals = hmap.values()
    rkeys = rassert.keys()
    rvals = rassert.values()

    #total number of rtypes for each node
    tr1 = len(nc1.keys())
    tr2 = len(nc2.keys())

    #total number of relationships for each node
    sr1 = len(cnode.outgoing_relations) + len(cnode.incoming_relations)
    sr2 = len(tnode.outgoing_relations) + len(tnode.incoming_relations)

    # for each mh, pick the best then pick the next best non-conflicting
    # total number of hypotheses is O(m*n) with max(n,m) matches
    # total score is based on possible non-conflicts
    # only penalize on true conflicts
    # max possible matches is min(n,m) matches

    if cluster_mode == 0:
        maxm = min(sr1,sr2)
    else:
        maxm = min(tr1,tr2)

    for score, r1, src, r2, target, v1, v2 in get_hypotheses():
        vkey = (src, v1)
        rkey1 = (r1, v1)
        rkey2 = (r2, v2)

        if v1:
            if v2:
                otype = "OUT-OUT"
            else:
                otype = "OUT-IN"
        else:
            if v2:
                otype = "IN-OUT"
            else:
                otype = "IN-IN"

        #same src, dest could have multiple rtype mappings
        '''
        1 to many
        '''
        #if new concept mapping
        if vkey not in hkeys and target not in hvals:
            #if new rtype mapping
            if rkey1 not in rkeys and rkey2 not in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            elif rkey1 not in rkeys and rkey2 in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            #if rtype mapping exists but is consistent
            elif rassert.get(rkey1) == rkey2:
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
        elif vkey not in hkeys and target in hvals:
            #if new rtype mapping
            if rkey1 not in rkeys and rkey2 not in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            elif rkey1 not in rkeys and rkey2 in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            #if rtype mapping exists but is consistent
            elif rassert.get(rkey1) == rkey2:
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
        #if existing concept mapping
        elif hmap.get(vkey) == target:
            #if new rtype mapping
            if rkey1 not in rkeys and rkey2 not in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            elif rkey1 not in rkeys and rkey2 in rvals:
                rassert[rkey1] = rkey2
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
            #if rtype mapping exists but is consistent
            elif rassert.get(rkey1) == rkey2:
                hmap[vkey] = target
                best[(otype, r1, src)] = (r2, target, score)
                rating += score
        total_rating += 1/maxm

    #get max number of each (ideal number)
    v = max(sr1, sr2)
    z = max(tr1, tr2)

    #total impact of the analogy (in terms of connectivity)
    weight = z*v

    try:
        confidence = 1 - (abs(tr1-tr2)/z + abs(sr1-sr2)/v)/2
    except ZeroDivisionError:
        confidence = 0

    try:
        normalized_rating = rating / total_rating
    except ZeroDivisionError:
        normalized_rating = 0

    #total_score = (confidence + normalized_rating) / 2
    total_score = confidence * normalized_rating

    return {"total_score":total_score,
            "confidence":confidence,
            "rating":normalized_rating,
            "src_concept":src_concept,
            "target_concept":target_concept,
            "asserts":rassert,
            "mapping":best,
            "weight":weight,
            "cluster_mode":cluster_mode}

def find_best_analogy(src_concept, src_domain, target_domain, filter_list=None,
                      rmax=1, vmax=1, cluster_mode=False, cluster_threshold=100,
                      knn_filter=None):
    """Finds the best analogy between a specific concept in the source domain
    and any concept in the target domain.

    If filter_list is specified, only the concepts in that list will be
    selected from to make analogies.

    In cluster mode, the analogy will be computed using a single example of
    each relationship type, weighted appropriately. This is useful for nodes
    with a very large number of homogeneous connections as it severely cuts
    down on the computation time.

    0 = default (no clustering)
    1 = source domain clustering only
    2 = target domain clustering only
    3 = both domains will be clustered
    4 = anything with a high enough knowledge level will be clustered. Determined
    by <cluster_threshold>, default is 100.

    If knn_filter is specified, only concepts from the <knn_filter> nearest
    neighbors will be selected from to make analogies.

    Note: analogies to self are ignored (if same domain)

    raises an AnalogyException if concept does not exist in domain
    """

    if not src_concept in src_domain.nodes:
        raise AnalogyException("'%s' not in source domain" % src_concept)

    if filter_list != None:
        candidate_pool = filter_list
    elif knn_filter != None:
        candidate_pool = [c for d,c in target_domain.get_closest_node(
            src_domain.node_vectors[src_concept], knn_filter)]
    else:
        candidate_pool = target_domain.nodes



    best_result = None
    best_score = 0

    ikl = src_domain.nodes[src_concept].knowledge_level

    for target_concept in candidate_pool:
        # find novel within same domain
        # otherwise best analogy would always be self
        if target_domain == src_domain and target_concept == src_concept:
            continue

        ckl = target_domain.nodes[target_concept].knowledge_level

        cmode = cluster_mode

        if cluster_mode == 4:
            if ikl > cluster_threshold:
                if ckl > cluster_threshold:
                    cmode = 3
                else:
                    cmode = 1
            elif ckl > cluster_threshold:
                cmode = 2
            else:
                cmode = 0

        result = make_analogy(src_concept, src_domain, target_concept,
                              target_domain, rmax, vmax, cmode)
        if result["total_score"] > best_score:
            best_result = result
            best_score = result["total_score"]

    return best_result


def get_all_analogies(src_concept, src_domain, target_domain, filter_list=None,
                      rmax=1, vmax=1, cluster_mode=False, cluster_threshold=100):
    """Makes all analogies for some concept in one domain to another domain

    Finds all analogies between a specific concept in the source domain
    and any concept in the target domain.

    If filter_list is specified, only the concepts in that list will be
    selected from to make analogies.

    In cluster mode, the analogy will be computed using a single example of
    each relationship type, weighted appropriately. This is useful for nodes
    with a very large number of homogeneous connections as it severely cuts
    down on the computation time.

    0 = default (no clustering)
    1 = source domain clustering only
    2 = target domain clustering only
    3 = both domains will be clustered
    4 = anything with a high enough knowledge level will be clustered. Determined
    by <cluster_threshold>, default is 100.

    raises an AnalogyException if concept does not exist in domain
    """

    candidate_pool = filter_list if filter_list is not None else target_domain.nodes
    results = []
    ikl = src_domain.nodes[src_concept].knowledge_level

    if not src_concept in src_domain.nodes:
        raise AnalogyException("'%s' not in source domain" % src_concept)

    for target_concept in candidate_pool:

        ckl = target_domain.nodes[target_concept].knowledge_level

        cmode = cluster_mode

        if cluster_mode == 4:
            if ikl > cluster_threshold:
                if ckl > cluster_threshold:
                    cmode = 3
                else:
                    cmode = 1
            elif ckl > cluster_threshold:
                cmode = 2
            else:
                cmode = 0

        result = make_analogy(src_concept, src_domain, target_concept,
                              target_domain, rmax, vmax, cmode)
        if result:
            results.append(result)

    return results


def explain_analogy(analogy, verbose=False, paragraph=True):

    """
    Takes an analogy and returns an explanation.

    If verbose is True, it will explain everything. Otherwise it
    will only explain one of each relationship type.

    If paragraph is True, it will return a paragraph. Otherwise it will
    return the individual logic chunks.

    """


    # only explain main relation
    if not analogy:
        return

    src = analogy["src_concept"]
    trg = analogy["target_concept"]
    mapping = analogy["mapping"]
    cluster_mode = analogy["cluster_mode"]

    narrative = ""
    narrative += "\t'%s' is like '%s'. " % (src, trg)
    narrative += "This is because"
    nchunks = []

    mentioned = set()

    for (x, r1, d1), (r2, d2, s) in mapping.items():
        if not verbose and (r1,r2) in mentioned:
            continue

        if cluster_mode == 0:#no clustering
            if x == "IN-IN":
                nchunks.append((s, d1, r1, src, d2, r2, trg))
            if x == "IN-OUT":
                nchunks.append((s, d1, r1, src, trg, r2, d2))
            if x == "OUT-IN":
                nchunks.append((s, src, r1, d1, d2, r2, trg))
            if x == "OUT-OUT":
                nchunks.append((s, src, r1, d1, trg, r2, d2))
        elif cluster_mode == 1:#src only cluster
            if x == "IN-IN" or x == "OUT-IN":
                nchunks.append((s, d1, r1, src, d2, r2, trg))
            if x == "IN-OUT" or x == "OUT-OUT":
                nchunks.append((s, d1, r1, src, trg, r2, d2))
        elif cluster_mode == 2:#target only cluster
            if x == "IN-IN" or x == "IN-OUT":
                nchunks.append((s, d1, r1, src, d2, r2, trg))
            if x == "OUT-IN" or x == "OUT-OUT":
                nchunks.append((s, src, r1, d1, d2, r2, trg))
        elif cluster_mode == 3:#both clustered
            nchunks.append((s, d1, r1, src, d2, r2, trg))
        mentioned.add((r1,r2))
    nchunks.sort(reverse=True)

    if not paragraph:
        return nchunks

    #order by score to give most important matches first
    for i, nc in enumerate(nchunks):
        s, a, b, c, d, e, f = nc
        if i == len(nchunks) - 1:
            if i > 1: #only add 'and' if more than one thing
                narrative += " and"
            if cluster_mode == 0:#no clustering
                narrative += " %s <%s> %s in the same"\
                             " way that %s <%s> %s.\n"%(a, b, c, d, e, f)
            elif cluster_mode == 1:#src only cluster
                narrative += " %s %s just like %s <%s> %s.\n"%(a, c, d, e, f)
            elif cluster_mode == 2:#target only cluster
                narrative += " %s <%s> %s just like %s %s.\n"%(a, b, c, d, f)
            elif cluster_mode == 3:#both clustered
                narrative += " %s %s just like %s %s.\n"%(a, c, d, f)
        else:
            if cluster_mode == 0:#no clustering
                narrative += " %s <%s> %s in the same"\
                             " way that %s <%s> %s,"%(a, b, c, d, e, f)
            if cluster_mode == 1:#src only cluster
                narrative += " %s %s just like %s <%s> %s,"%(a, c, d, e, f)
            if cluster_mode == 2:#target only cluster
                narrative += " %s <%s> %s just like %s %s,"%(a, b, c, d, f)
            elif cluster_mode == 3:#both clustered
                narrative += " %s %s just like %s %s,"%(a, c, d, f)
    return narrative
