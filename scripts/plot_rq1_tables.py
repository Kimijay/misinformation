import json
import glob
import os
from collections import defaultdict, deque
from statistics import mean, median
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

MIS_PATTERNS = ['data_by_type/jsonl/misinformation.jsonl']
VER_PATTERNS = ['data_by_type/jsonl/verified_information.part.*.jsonl']


def setup_chinese_font():
    """Try to set a Chinese-capable font for titles/headers."""
    candidates = [
        'Noto Sans CJK SC', 'Noto Sans CJK JP', 'Noto Sans SC', 'Source Han Sans SC',
        'Microsoft YaHei', 'SimHei', 'WenQuanYi Zen Hei', 'PingFang SC'
    ]
    # Try loading common CJK font files first.
    font_files = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
    ]
    for fp in font_files:
        if os.path.exists(fp):
            try:
                font_manager.fontManager.addfont(fp)
            except Exception:
                pass

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            rcParams['axes.unicode_minus'] = False
            return name
    # Fallback: keep default if no Chinese font found.
    rcParams['axes.unicode_minus'] = False
    return None


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
    table.scale(1, 1.55)

    # 三线表样式：默认无边框，仅保留顶部线、表头下线、底部线。
    cells = table.get_celld()
    rows = len(table_data) + 1  # + header
    cols = len(col_labels)

    for (r, c), cell in cells.items():
        cell.set_linewidth(0.0)
        cell.visible_edges = ''
        cell.set_edgecolor('black')

    # top rule + mid rule on header row
    for c in range(cols):
        hcell = cells[(0, c)]
        hcell.visible_edges = 'TB'
        hcell.set_linewidth(1.1)

    # bottom rule on last row
    for c in range(cols):
        bcell = cells[(rows - 1, c)]
        bcell.visible_edges = 'B'
        bcell.set_linewidth(1.1)

    plt.title(title, fontsize=14, pad=14)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)


def main():
    font_used = setup_chinese_font()
    if font_used:
        print(f'Using font: {font_used}')
    else:
        print('Warning: No dedicated Chinese font found; rendering may depend on environment defaults.')

    mis = collect(MIS_PATTERNS)
    ver = collect(VER_PATTERNS)

    # Table 1
    metrics = [
        ('转发节点数', 'repost_nodes', '真实信息更高（常态）'),
        ('转发边数', 'repost_edges', '真实信息更高'),
        ('传播深度', 'depth', '真实信息更高（均值）'),
        ('最大层宽', 'width', '真实信息更高'),
        ('评论线程数', 'comment_threads', '真实信息更高'),
        ('评论节点数', 'comment_nodes', '真实信息更高'),
        ('评论边数', 'comment_edges', '真实信息更高'),
    ]

    t1 = []
    for zh, key, direction in metrics:
        t1.append([zh, summary_str(mis[key]), summary_str(ver[key]), direction])

    draw_table(
        table_data=t1,
        col_labels=['指标', '虚假信息（N=7560）\n均值/中位数/P90/最大值', '真实信息（N=8317）\n均值/中位数/P90/最大值', '差异方向'],
        title='表1 真假信息传播结构指标描述统计',
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
        ['转发节点数=0 占比', f'{mis_repost0:.2%}', f'{ver_repost0:.2%}'],
        ['评论节点数=0 占比', f'{mis_comment0:.2%}', f'{ver_comment0:.2%}'],
        ['深传播（深度≥3）占比', f'{mis_deep3:.2%}', f'{ver_deep3:.2%}'],
        ['大规模扩散（转发节点≥100）占比', f'{mis_large100:.2%}', f'{ver_large100:.2%}'],
        ['最大转发节点', f"{max(mis['repost_nodes'])}", f"{max(ver['repost_nodes'])}"],
        ['最大传播深度', f"{max(mis['depth'])}", f"{max(ver['depth'])}"],
    ]

    draw_table(
        table_data=t2,
        col_labels=['风险/结构指标', '虚假信息', '真实信息'],
        title='表2 真假信息结构风险与失败率比较',
        out_path='docs/figures/rq1_table2.png',
        fig_size=(14, 4.8)
    )

    print('Generated: docs/figures/rq1_table1.png')
    print('Generated: docs/figures/rq1_table2.png')


if __name__ == '__main__':
    main()
