import numpy as np

def is_Dom(Adj, xD, N):
    for k in np.arange(N):
        if (np.dot(Adj[k, :], xD) < 1):
            return False
    return True

def is_Min_Dom(Adj, xD, N):
    for l in np.arange(N):
        if xD[l] != 0:
            xD_l = xD.copy()
            xD_l[l] = 0
            if is_Dom(Adj, xD_l, N):
                return False
    return True

def find_Min_Dom(Adj, N):
    xD = np.ones(N, dtype=int)
    while not is_Min_Dom(Adj, xD, N):
        for s in np.arange(N):
            xD_s = xD.copy()
            xD_s[s] = 0
            if is_Dom(Adj, xD_s, N):
                xD = xD_s.copy()
    return xD

def find_Min_Dom_Vert_Weig(Adj, N):
    xD = np.ones(N, dtype=int)
    vertex_weights_argsorted = Adj.sum(axis=1).argsort()
    while not is_Min_Dom(Adj, xD, N):
        for s in vertex_weights_argsorted:
            xD_s = xD.copy()
            xD_s[s] = 0
            if is_Dom(Adj, xD_s, N):
                xD = xD_s.copy()
    return xD

def count_Cut_Weight(Adj, xD, N):
    w = 0
    for i in np.arange(N):
        if xD[i] == 1:
            for j in np.arange(N):
                if (xD[j] == 0):
                    w = w + Adj[i, j]
    return w

def create_adjacency_matrix(edges, n):
    adjacency_matrix = [[0] * n for i in range(n)]
    b = np.eye(n)
    for edge in edges:
        u, v = edge
        adjacency_matrix[u - 1][v - 1] = 1
        adjacency_matrix[v - 1][u - 1] = 1
    adjacency_matrix = adjacency_matrix + b
    return adjacency_matrix

def count_effective_weight(Adj, xD, N):
    ew = np.zeros(N, dtype=int)
    for i in np.arange(N):
        if xD[i] == 0:
            for j in np.arange(N):
                if xD[j] == 0:
                    ew[i] += (Adj - np.eye(N, dtype=int))[i, j]
                if xD[j] == 1:
                    ew[i] -= (Adj - np.eye(N, dtype=int))[i, j]
        if xD[i] == 1:
            ew[i] -= 100
    return ew

def add_positive_to_D(xD_, ew_, N):
    for i in np.arange(N):
        if xD_[i] == 0 and ew_[i] > 0:
            xD_[i] = 1
    return xD_

def add_fraction_of_positive_to_D(xD, ew, N, frac=0.5, q=0):
    # Защита от нечислового q
    try:
        q_val = float(q)
    except (TypeError, ValueError):
        q_val = 0
    cardinality_of_U = q_val if q_val > 0 else max(1.0, np.floor(np.sum([ew > 0]) * frac))
    order = np.arange(int(cardinality_of_U), dtype=int)
    np.random.shuffle(order)
    for i in order:
        pos = ew.argsort()[::-1][i]
        xD[pos] = 1
    return xD

def add_n_rand_to_D(xD, n, N):
    for i in np.arange(n):
        sh = np.nonzero(xD == 0)[0]
        np.random.shuffle(sh)
        xD[sh[i]] = 1
    return xD

def reduce_to_Min_Dom_Vert_Weig(Adj, xD, N):
    arr = np.arange(N)
    np.random.shuffle(arr)
    while not is_Min_Dom(Adj, xD, N):
        for s in arr:
            xD_s = xD.copy()
            xD_s[s] = 0
            if is_Dom(Adj, xD_s, N):
                xD = xD_s.copy()
    return xD

def do_n_launches_capped(Adj_w, N_launches, N_solutions, frac, q, cap, vocal=True):
    # Защита от нечисловых аргументов
    try:
        N_launches = int(N_launches)
        N_solutions = int(N_solutions)
        frac = float(frac)
        q_val = float(q)
        cap = int(cap)
    except (TypeError, ValueError):
        N_launches = 10
        N_solutions = 100
        frac = 0.35
        q_val = 1.0
        cap = 1000

    N = Adj_w.shape[0]
    if vocal:
        print(f"    Алгоритм: N={N}, запусков={N_launches}, решений={N_solutions}")
    counter = 0
    plot_sol_to_sol = []
    xD_best_all_launches = np.zeros(N, dtype=int)
    w_max_all_launches = 0

    for u in range(N_launches):
        if vocal:
            print(f"    Запуск {u + 1}/{N_launches}...")
        xD_buff = reduce_to_Min_Dom_Vert_Weig(Adj_w, np.ones(N, dtype=int), N)
        cw_buff = count_Cut_Weight(Adj_w, xD_buff.copy(), N)

        xD_best_loc = np.zeros(N, dtype=int)
        cw_best_loc = 0

        xD_best = np.ones(N, dtype=int)
        cw_best = count_Cut_Weight(Adj_w, xD_best.copy(), N)

        sol_count = 0
        while sol_count < N_solutions:
            ew_t = count_effective_weight(Adj_w, xD_buff.copy(), N)
            xD_t = add_fraction_of_positive_to_D(xD_buff.copy(), ew_t.copy(), N, frac=frac, q=q_val)
            xD_t = reduce_to_Min_Dom_Vert_Weig(Adj_w, xD_t.copy(), N)
            cw_of_xD_t = count_Cut_Weight(Adj_w, xD_t, N)

            if cw_of_xD_t >= cw_buff:
                sol_count += 1
                xD_buff = xD_t.copy()
                cw_buff = cw_of_xD_t
                plot_sol_to_sol.append(cw_buff)
                xD_best_loc = np.ones(N, dtype=int)
                cw_best_loc = 0
                counter = 0

                if cw_buff >= cw_best:
                    xD_best = xD_buff.copy()
                    cw_best = cw_buff

            if cw_of_xD_t >= cw_best_loc:
                xD_best_loc = xD_t.copy()
                cw_best_loc = cw_of_xD_t

            if counter >= cap:
                xD_buff = xD_best_loc.copy()
                cw_buff = cw_best_loc
                plot_sol_to_sol.append(cw_buff)
                xD_best_loc = np.ones(N, dtype=int)
                cw_best_loc = 0
                sol_count += 1
                counter = 0

            counter += 1

        if w_max_all_launches <= cw_best:
            w_max_all_launches = cw_best
            xD_best_all_launches = xD_best

        if vocal:
            print(f'Запуск {u + 1} завершен, максимальный вес: {cw_best}')

    return w_max_all_launches, xD_best_all_launches, plot_sol_to_sol