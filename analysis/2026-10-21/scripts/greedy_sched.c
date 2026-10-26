/*
 * タイルQR (フラットツリー, TS カーネル) の DAG を p コアで貪欲スケジューリングし、
 * 並列効率 eta = W / (p * T_p) を出す。DAG の定義は dag.py と同一。
 *
 *   variant 0 = bouwmeester (RAW のみ)
 *   variant 1 = plasma      (UNMQR(k,*) -> TSQRT(k+1,k) の WAR を追加)
 *   policy  0 = FIFO        (実行可能になった時刻順、同時刻は PLASMA の投入順)
 *   policy  1 = CP          (最長残り経路 bottom-level の長い順)
 *
 * 通信・メモリ・タスク生成オーバーヘッドは入れない。カーネル重みは 4/6/6/12 固定
 * (全カーネルが同じ flop 効率で動くと仮定)。
 *
 * usage: greedy_sched variant policy Nmax p1 [p2 ...]
 * 出力 : N p W D Tp eta  (N = 1..Nmax)
 *
 * build: gcc -O2 -o greedy_sched greedy_sched.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int w, npred, nsucc, *succ; long bl; } Task;

static int N_, VAR;
static Task *T;
static int ntask;
static int *id_geqrt, *id_unmqr, *id_tsqrt, *id_tsmqr; /* index tables */


#define IG(k)       id_geqrt[(k)]
#define IU(k,n)     id_unmqr[(k)*N_+(n)]
#define IT(m,k)     id_tsqrt[(m)*N_+(k)]
#define IS(m,n,k)   id_tsmqr[((long)(k)*N_+(m))*N_+(n)]

/* edge list */
static int *eu, *ev; static long ne, cape;
static void edge(int u, int v) {
    if (u < 0) return;
    if (ne == cape) { cape = cape ? cape*2 : 1<<20; eu = realloc(eu, cape*sizeof(int)); ev = realloc(ev, cape*sizeof(int)); }
    eu[ne] = u; ev[ne] = v; ne++;
}

static int newtask(int w) { T[ntask].w = w; T[ntask].npred = 0; T[ntask].nsucc = 0; return ntask++; }

static void build(int N) {
    N_ = N; ntask = 0; ne = 0;
    long maxt = (long)N*N*N + 4L*N*N + 8;
    T = calloc(maxt, sizeof(Task));
    id_geqrt = malloc(N*sizeof(int));
    id_unmqr = malloc((long)N*N*sizeof(int));
    id_tsqrt = malloc((long)N*N*sizeof(int));
    id_tsmqr = malloc((long)N*N*N*sizeof(int));
    for (int k = 0; k < N; k++) {
        #define PREV(m,n) ((k) > 0 ? IS((m),(n),(k)-1) : -1)
        int g = IG(k) = newtask(4);
        edge(PREV(k,k), g);
        for (int n = k+1; n < N; n++) { int u = IU(k,n) = newtask(6); edge(g,u); edge(PREV(k,n),u); }
        for (int m = k+1; m < N; m++) {
            int t = IT(m,k) = newtask(6);
            edge(m == k+1 ? g : IT(m-1,k), t);
            edge(PREV(m,k), t);
            if (VAR == 1 && m == k+1) for (int n = k+1; n < N; n++) edge(IU(k,n), t);
            for (int n = k+1; n < N; n++) {
                int s = IS(m,n,k) = newtask(12);
                edge(t, s);
                edge(m == k+1 ? IU(k,n) : IS(m-1,n,k), s);
                edge(PREV(m,n), s);
            }
        }
    }
    /* CSR successors */
    for (long e = 0; e < ne; e++) { T[eu[e]].nsucc++; T[ev[e]].npred++; }
    int *buf = malloc((ne+1)*sizeof(int)); long off = 0;
    for (int i = 0; i < ntask; i++) { T[i].succ = buf + off; off += T[i].nsucc; T[i].nsucc = 0; }
    for (long e = 0; e < ne; e++) { Task *a = &T[eu[e]]; a->succ[a->nsucc++] = ev[e]; }
    /* bottom level (投入順がトポロジカル順なので逆順に走査) */
    for (int i = ntask-1; i >= 0; i--) {
        long b = 0;
        for (int j = 0; j < T[i].nsucc; j++) if (T[T[i].succ[j]].bl > b) b = T[T[i].succ[j]].bl;
        T[i].bl = b + T[i].w;
    }
}

static void freeall(void) {
    free(T[0].succ); free(T); free(id_geqrt); free(id_unmqr); free(id_tsqrt); free(id_tsmqr);
}

/* ---- binary heap of (key1, key2, id), min-heap ---- */
typedef struct { long a, b; int id; } HE;
typedef struct { HE *h; int n, cap; } Heap;
static int lt(HE x, HE y) { return x.a < y.a || (x.a == y.a && x.b < y.b); }
static void hpush(Heap *H, HE e) {
    if (H->n == H->cap) { H->cap = H->cap ? H->cap*2 : 1024; H->h = realloc(H->h, H->cap*sizeof(HE)); }
    int i = H->n++; H->h[i] = e;
    while (i > 0) { int p = (i-1)/2; if (!lt(H->h[i], H->h[p])) break; HE t = H->h[i]; H->h[i] = H->h[p]; H->h[p] = t; i = p; }
}
static HE hpop(Heap *H) {
    HE top = H->h[0]; H->h[0] = H->h[--H->n]; int i = 0;
    for (;;) { int l = 2*i+1, r = l+1, s = i;
        if (l < H->n && lt(H->h[l], H->h[s])) s = l;
        if (r < H->n && lt(H->h[r], H->h[s])) s = r;
        if (s == i) break;
        HE t = H->h[i]; H->h[i] = H->h[s]; H->h[s] = t; i = s; }
    return top;
}

static long simulate(int p, int policy) {
    int *rem = malloc(ntask*sizeof(int));
    for (int i = 0; i < ntask; i++) rem[i] = T[i].npred;
    Heap ready = {0}, run = {0};
    for (int i = 0; i < ntask; i++) if (!rem[i]) hpush(&ready, (HE){ policy ? -T[i].bl : 0, i, i });
    long now = 0; int busy = 0, done = 0;
    while (done < ntask) {
        while (busy < p && ready.n) { HE e = hpop(&ready); hpush(&run, (HE){ now + T[e.id].w, e.id, e.id }); busy++; }
        HE f = hpop(&run); now = f.a; busy--; done++;
        /* 同時刻に終わるものをまとめて回収 */
        int fin[4096]; int nf = 0; fin[nf++] = f.id;
        while (run.n && run.h[0].a == now && nf < 4096) { fin[nf++] = hpop(&run).id; busy--; done++; }
        for (int q = 0; q < nf; q++) {
            Task *t = &T[fin[q]];
            for (int j = 0; j < t->nsucc; j++) { int s = t->succ[j];
                if (--rem[s] == 0) hpush(&ready, (HE){ policy ? -T[s].bl : now, s, s }); }
        }
    }
    free(rem); free(ready.h); free(run.h);
    return now;
}

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage: %s variant policy Nmax p1 [p2...]\n", argv[0]); return 1; }
    VAR = atoi(argv[1]); int policy = atoi(argv[2]); int Nmax = atoi(argv[3]);
    printf("N p W D Tp eta\n");
    for (int N = 1; N <= Nmax; N++) {
        build(N);
        long W = 0, D = 0;
        for (int i = 0; i < ntask; i++) { W += T[i].w; if (T[i].bl > D) D = T[i].bl; }
        for (int a = 4; a < argc; a++) {
            int p = atoi(argv[a]);
            long Tp = simulate(p, policy);
            printf("%d %d %ld %ld %ld %.6f\n", N, p, W, D, Tp, (double)W / ((double)p * Tp));
        }
        fflush(stdout);
        freeall();
    }
    return 0;
}
