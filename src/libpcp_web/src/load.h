/*
 * Copyright (c) 2017-2018 Red Hat.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * for more details.
 */
#ifndef SERIES_LOAD_H
#define SERIES_LOAD_H

#include "pmapi.h"
#include "series.h"

typedef struct seriesname {
    sds			sds;		/* external sds for this series */
    long long		mapid;		/* internal string identifiers */
    unsigned char	hash[20];	/* SHA1 of intrinsic metadata */
} seriesname_t;

typedef struct context {
    seriesname_t	name;		/* source archive or hostspec */
    sds			host;		/* hostname from archive/host */
    sds			origin;		/* host where series loaded in */
    long long		hostid;		/* hostname source identifier */
    double		location[2];	/* latitude and longitude */
    unsigned int	type	: 7;
    unsigned int	cached	: 1;
    int			context;	/* PMAPI context */
    int			nmetrics;
    const char		**metrics;	/* metric specification strings */
    pmLabelSet		*labels;
} context_t;

typedef struct domain {
    unsigned int	domain;
    context_t		*context;
    pmLabelSet		*labels;
} domain_t;

typedef struct labellist {
    long long		nameid;
    long long		valueid;
    sds			name;
    sds			value;
    unsigned int	flags;
    struct labellist	*next;
    struct dict		*valuemap;
    void		*arg;
} labellist_t;

typedef struct instance {
    seriesname_t	name;		/* instance naming information */
    unsigned int	inst;		/* internal instance identifier */
    pmLabelSet		*labels;	/* instance labels or NULL */
    labellist_t		*labellist;	/* label name/value mapping set */
} instance_t;

typedef struct indom {
    pmInDom		indom;
    domain_t		*domain;
    pmLabelSet		*labels;
    struct dict		*insts;		/* map identifiers to instances */
} indom_t;

typedef struct cluster {
    unsigned int	cluster;
    domain_t		*domain;
    pmLabelSet		*labels;
} cluster_t;

typedef struct value {
    int			inst;		/* internal instance identifier */
    unsigned int	updated;	/* last sample modified value */
    pmAtomValue		atom;		/* most recent sampled value */
} value_t;

typedef struct valuelist {
    unsigned int	listsize;	/* high-water-mark inst count */
    unsigned int	listcount;	/* currently init'd inst count */
    value_t		value[0];
} valuelist_t;

typedef struct metric {
    pmDesc		desc;
    cluster_t		*cluster;
    indom_t		*indom;
    pmLabelSet		*labels;	/* metric item labels or NULL */
    labellist_t		*labellist;	/* label name/value mapping set */
    seriesname_t	*names;		/* metric names and mappings */
    unsigned int	numnames : 16;	/* count of metric PMNS entries */
    unsigned int	padding : 14;	/* zero-fill structure padding */
    unsigned int	updated : 1;	/* last sample returned success */
    unsigned int	cached : 1;	/* metadata is already cached */
    int			error;		/* a PMAPI negative error code */
    union {
	pmAtomValue	atom;		/* singleton value (PM_IN_NULL) */
	valuelist_t	*vlist;		/* instance values and metadata */
    } u;
} metric_t;

struct seriesLoadBaton;
extern void doneSeriesLoadBaton(struct seriesLoadBaton *);

extern pmSeriesInfoCallBack seriesLoadBatonInfo(struct seriesLoadBaton *);
extern context_t *seriesLoadBatonContext(struct seriesLoadBaton *);
extern void seriesLoadBatonFetch(struct seriesLoadBaton *);

extern void *findID(struct dict *, void *);

#endif	/* SERIES_LOAD_H */
