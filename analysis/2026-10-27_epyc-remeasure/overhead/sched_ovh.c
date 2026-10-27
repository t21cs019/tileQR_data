/*
 * タイルQR（フラットツリー, TS, PLASMA の依存 = greedy_sched.c の variant 1）を
 * p コアで FIFO スケジューリングし、実行時間 Tp（秒）を出す。
 * greedy_sched.c との違い:
 *   - カーネル時間は実数（秒）で与える。端のタイル（幅 e*nb）は寸法比で縮める
 *   - タスク1個ごとにコアを o 秒余分に占有する（生成・取り出しなどのコスト）
 *   - 依存が解けてから L 秒たたないと実行可能にならない（起床・受け渡しの遅れ）
 *
 * usage: sched_ovh N efrac p tGEQRT tUNMQR tTSQRT tTSMQR nO o1..oK nL L1..Lm
 * 出力 : o L Tp  （全組み合わせ）
 */
#include <stdio.h>
#include <stdlib.h>

typedef struct { double w; int npred, nsucc, *succ; } Task;
static Task *T; static int ntask, N_;
static int *ig, *iu, *it, *is;
#define IG(k) ig[(k)]
#define IU(k,n) iu[(k)*N_+(n)]
#define IT(m,k) it[(m)*N_+(k)]
#define IS(m,n,k) is[((long)(k)*N_+(m))*N_+(n)]
static int *eu, *ev; static long ne, cape;
static void edge(int u, int v) {
    if (u < 0) return;
    if (ne == cape) { cape = cape ? cape*2 : 1<<20; eu = realloc(eu, cape*sizeof(int)); ev = realloc(ev, cape*sizeof(int)); }
    eu[ne] = u; ev[ne] = v; ne++;
}
static int newtask(double w) { T[ntask].w = w; return ntask++; }

static void build(int N, double e, const double *tk) {
    N_ = N;
    long maxt = (long)N*N*N + 4L*N*N + 8;
    T = calloc(maxt, sizeof(Task));
    ig = malloc(N*sizeof(int)); iu = malloc((long)N*N*sizeof(int));
    it = malloc((long)N*N*sizeof(int)); is = malloc((long)N*N*N*sizeof(int));
    #define F(i) ((i) == N-1 ? e : 1.0)
    for (int k = 0; k < N; k++) {
        #define PREV(m,n) ((k) > 0 ? IS((m),(n),(k)-1) : -1)
        int g = IG(k) = newtask(tk[0]*F(k)*F(k)*F(k));
        edge(PREV(k,k), g);
        for (int n = k+1; n < N; n++) { int u = IU(k,n) = newtask(tk[1]*F(k)*F(k)*F(n)); edge(g,u); edge(PREV(k,n),u); }
        for (int m = k+1; m < N; m++) {
            int t = IT(m,k) = newtask(tk[2]*F(m)*F(k)*F(k));
            edge(m == k+1 ? g : IT(m-1,k), t);
            edge(PREV(m,k), t);
            if (m == k+1) for (int n = k+1; n < N; n++) edge(IU(k,n), t);   /* PLASMA の WAR */
            for (int n = k+1; n < N; n++) {
                int s = IS(m,n,k) = newtask(tk[3]*F(m)*F(n)*F(k));
                edge(t, s);
                edge(m == k+1 ? IU(k,n) : IS(m-1,n,k), s);
                edge(PREV(m,n), s);
            }
        }
    }
    for (long i = 0; i < ne; i++) { T[eu[i]].nsucc++; T[ev[i]].npred++; }
    int *buf = malloc((ne+1)*sizeof(int)); long off = 0;
    for (int i = 0; i < ntask; i++) { T[i].succ = buf + off; off += T[i].nsucc; T[i].nsucc = 0; }
    for (long i = 0; i < ne; i++) { Task *a = &T[eu[i]]; a->succ[a->nsucc++] = ev[i]; }
}

typedef struct { double a; int id; } HE;
typedef struct { HE *h; int n, cap; } Heap;
static int lt(HE x, HE y) { return x.a < y.a || (x.a == y.a && x.id < y.id); }
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

static double simulate(int p, double o, double L) {
    int *rem = malloc(ntask*sizeof(int));
    for (int i = 0; i < ntask; i++) rem[i] = T[i].npred;
    Heap ready = {0}, run = {0};
    for (int i = 0; i < ntask; i++) if (!rem[i]) hpush(&ready, (HE){ L, i });
    double now = 0; int busy = 0, done = 0;
    while (done < ntask) {
        while (busy < p && ready.n && ready.h[0].a <= now) {
            HE e = hpop(&ready); hpush(&run, (HE){ now + T[e.id].w + o, e.id }); busy++;
        }
        double nr = (busy < p && ready.n) ? ready.h[0].a : 1e300;
        if (run.n && run.h[0].a <= nr) {
            HE f = hpop(&run); now = f.a; busy--; done++;
            Task *t = &T[f.id];
            for (int j = 0; j < t->nsucc; j++) { int s = t->succ[j];
                if (--rem[s] == 0) hpush(&ready, (HE){ now + L, s }); }
        } else {
            now = nr;
        }
    }
    free(rem); free(ready.h); free(run.h);
    return now;
}

int main(int argc, char **argv) {
    int a = 1;
    int N = atoi(argv[a++]); double e = atof(argv[a++]); int p = atoi(argv[a++]);
    double tk[4]; for (int i = 0; i < 4; i++) tk[i] = atof(argv[a++]);
    int nO = atoi(argv[a++]); double *O = malloc(nO*sizeof(double)); for (int i = 0; i < nO; i++) O[i] = atof(argv[a++]);
    int nL = atoi(argv[a++]); double *Ls = malloc(nL*sizeof(double)); for (int i = 0; i < nL; i++) Ls[i] = atof(argv[a++]);
    build(N, e, tk);
    for (int i = 0; i < nO; i++) for (int j = 0; j < nL; j++)
        printf("%g %g %.9g\n", O[i], Ls[j], simulate(p, O[i], Ls[j]));
    return 0;
}
