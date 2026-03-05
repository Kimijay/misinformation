import json
import glob
from collections import defaultdict, deque
from statistics import mean, median
import matplotlib.pyplot as plt

MIS_PATTERNS = ['data_by_type/jsonl/misinformation.jsonl']
VER_PATTERNS = ['data_by_type/jsonl/verified_information.part.*.jsonl']


def iter_records(patterns):
    for p in patterns:
        for fn in sorted(glob.glob(p)):
            with open(fn, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)


def count_nonnull(lst):
    return sum(1 for x in lst if x is not None)


def valid_edges(edges, n):
    out = []
    for e in edges:
        if isinstance(e, list) and len(e) == 2 and all(isinstance(i, int) for i in e):
            a, b = e
            if 0 <= a < n and 0 <= b < n:
                out.append((a, b))
    return out


def depth_and_width(n, edges):
    children = defaultdict(list)
    indeg = [0] * n
    for c, p in edges:
        children[p].append(c)
        indeg[c] += 1
    roots = [i for i in range(n) if indeg[i] == 0]
    if not roots and n > 0:
        roots = [0]

    depth = [-1] * n
    q = deque()
    for r in roots:
        depth[r] = 0
        q.append(r)

    while q:
        u = q.popleft()
        for v in children.get(u, []):
            if depth[v] < depth[u] + 1:
                depth[v] = depth[u] + 1
                q.append(v)

    reached = [d for d in depth if d >= 0]
    max_depth = max(reached) if reached else 0
    layers = defaultdict(int)
    for d in reached:
        layers[d] += 1
    max_width = max(layers.values()) if layers else 0
    return max_depth, max_width


def q(v, p):
    s = sorted(v)
    i = int((len(s) - 1) * p)
    return s[i]


def collect(patterns):
    vals = defaultdict(list)
    for r in iter_records(patterns):
        rg = r['repost_graph']
        n_total = len(rg.get('nodes', []))
        n_non = count_nonnull(rg.get('nodes', []))
        edges = valid_edges(rg.get('edges', []), n_total)
        m = len(edges)
        d, w = depth_and_width(n_total, edges) if n_total else (0, 0)

        comment_graphs = r.get('comment_graphs', [])
        c_threads = len(comment_graphs)
        c_nodes, c_edges = 0, 0
        for g in comment_graphs:
            gn = len(g.get('nodes', []))
            c_nodes += count_nonnull(g.get('nodes', []))
            c_edges += len(valid_edges(g.get('edges', []), gn))

        vals['repost_nodes'].append(n_non)
        vals['repost_edges'].append(m)
        vals['depth'].append(d)
        vals['width'].append(w)
        vals['comment_threads'].append(c_threads)
        vals['comment_nodes'].append(c_nodes)
        vals['comment_edges'].append(c_edges)
    return vals


def summary_str(v):
    return f"{mean(v):.2f} / {median(v):.0f} / {q(v,0.9):.0f} / {max(v):.0f}"


def draw_table(table_data, col_labels, title, out_path, fig_size=(16, 4.5), font_size=11):
    fig, ax = plt.subplots(figsize=fig_size)
    ax.axis('off')
    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.6)
    plt.title(title, fontsize=14, pad=14)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)


def main():
    mis = collect(MIS_PATTERNS)
    ver = collect(VER_PATTERNS)

    # Table 1
    metrics = [
        ('Repost nodes', 'repost_nodes', 'Verified > Misinformation (typical)'),
        ('Repost edges', 'repost_edges', 'Verified > Misinformation'),
        ('Cascade depth', 'depth', 'Verified > Misinformation (mean)'),
        ('Max layer width', 'width', 'Verified > Misinformation'),
        ('Comment threads', 'comment_threads', 'Verified > Misinformation'),
        ('Comment nodes', 'comment_nodes', 'Verified > Misinformation'),
        ('Comment edges', 'comment_edges', 'Verified > Misinformation'),
    ]

    t1 = []
    for zh, key, direction in metrics:
        t1.append([zh, summary_str(mis[key]), summary_str(ver[key]), direction])

    draw_table(
        table_data=t1,
        col_labels=['Metric', 'Misinformation (N=7560)\nMean / Median / P90 / Max', 'Verified (N=8317)\nMean / Median / P90 / Max', 'Direction'],
        title='Table 1. Descriptive statistics of propagation structure metrics',
        out_path='docs/figures/rq1_table1.png',
        fig_size=(18, 5.8)
    )

    # Table 2
    mis_repost0 = sum(v == 0 for v in mis['repost_nodes']) / len(mis['repost_nodes'])
    ver_repost0 = sum(v == 0 for v in ver['repost_nodes']) / len(ver['repost_nodes'])
    mis_comment0 = sum(v == 0 for v in mis['comment_nodes']) / len(mis['comment_nodes'])
    ver_comment0 = sum(v == 0 for v in ver['comment_nodes']) / len(ver['comment_nodes'])
    mis_deep3 = sum(v >= 3 for v in mis['depth']) / len(mis['depth'])
    ver_deep3 = sum(v >= 3 for v in ver['depth']) / len(ver['depth'])
    mis_large100 = sum(v >= 100 for v in mis['repost_nodes']) / len(mis['repost_nodes'])
    ver_large100 = sum(v >= 100 for v in ver['repost_nodes']) / len(ver['repost_nodes'])

    t2 = [
        ['Share with repost nodes = 0', f'{mis_repost0:.2%}', f'{ver_repost0:.2%}', 'Misinformation more likely to fail diffusion'],
        ['Share with comment nodes = 0', f'{mis_comment0:.2%}', f'{ver_comment0:.2%}', 'Misinformation more likely to fail discussion'],
        ['Share with depth >= 3', f'{mis_deep3:.2%}', f'{ver_deep3:.2%}', 'Verified more likely to be multi-layer cascades'],
        ['Share with repost nodes >= 100', f'{mis_large100:.2%}', f'{ver_large100:.2%}', 'Verified more often large-scale diffusion'],
        ['Max repost nodes', f"{max(mis['repost_nodes'])}", f"{max(ver['repost_nodes'])}", 'Misinformation has higher tail extreme'],
        ['Max cascade depth', f"{max(mis['depth'])}", f"{max(ver['depth'])}", 'Misinformation can have deeper single cases'],
    ]

    draw_table(
        table_data=t2,
        col_labels=['Risk / structure metric', 'Misinformation', 'Verified', 'Interpretation'],
        title='Table 2. Structural risk and failure-rate comparison',
        out_path='docs/figures/rq1_table2.png',
        fig_size=(16, 4.8)
    )

    print('Generated: docs/figures/rq1_table1.png')
    print('Generated: docs/figures/rq1_table2.png')


if __name__ == '__main__':
    main()
