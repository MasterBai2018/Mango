'use strict';

// ====================================================================
// 多语言翻译
// ====================================================================
allure.api.addTranslation('zh', {
    tab: { mango: { name: 'Mango 统计' } }
});
allure.api.addTranslation('en', {
    tab: { mango: { name: 'Mango Stats' } }
});

// ====================================================================
// 子 Tab 枚举
// ====================================================================
var SUBTAB_STATS   = 'mango-pane-stats';
var SUBTAB_REPORTS = 'mango-pane-reports';

// ====================================================================
// ─── 工具函数：测试统计渲染 ─────────────────────────────────────────
// ====================================================================

function computeStats(node) {
    // Allure 2.x 的 behaviors.json 节点本身没有预聚合的 statistic 字段，
    // 需要递归遍历 children，在叶节点（有 status 字段的测试用例）处统计。
    var total = 0, passed = 0, failed = 0, skipped = 0;

    function walk(n) {
        if (!n) return;
        if (n.status) {
            // 叶节点：测试用例
            total++;
            if      (n.status === 'passed')                         passed++;
            else if (n.status === 'failed' || n.status === 'broken') failed++;
            else if (n.status === 'skipped')                         skipped++;
            // 'unknown' 只计入 total
        } else if (n.children && n.children.length) {
            // 分类节点：递归
            n.children.forEach(walk);
        }
    }

    (node.children || []).forEach(walk);

    var rate      = total > 0 ? (passed / total * 100).toFixed(1) : '0.0';
    var isPassing = parseFloat(rate) >= 90;
    return { total: total, passed: passed, failed: failed, skipped: skipped, rate: rate, isPassing: isPassing };
}

function makeProgressBar(rate, isPassing) {
    var barClass = isPassing ? 'mango-bar-pass' : 'mango-bar-fail';
    var width = Math.min(100, Math.max(0, parseFloat(rate)));
    return '<div class="mango-progress">' +
               '<div class="mango-progress-fill ' + barClass + '" style="width:' + width + '%"></div>' +
               '<span class="mango-progress-label">' + rate + '%</span>' +
           '</div>';
}

function renderSuiteTable(suites) {
    if (!suites || suites.length === 0) {
        return '<p class="mango-empty">暂无 Suite 数据</p>';
    }
    var rows = suites.map(function (suite) {
        var s = computeStats(suite);
        // total=0 时显示中立状态，避免误显示 FAIL
        var rowCls, icon, statusText;
        if (s.total === 0) {
            rowCls     = '';
            icon       = '—';
            statusText = '—';
        } else if (s.isPassing) {
            rowCls     = 'mango-row-pass';
            icon       = '✅';
            statusText = 'PASS';
        } else {
            rowCls     = 'mango-row-fail';
            icon       = '❌';
            statusText = 'FAIL';
        }
        return '<tr class="' + rowCls + '">' +
            '<td class="mango-suite-name">' + (suite.name || '-') + '</td>' +
            '<td class="mango-num">'                             + s.total   + '</td>' +
            '<td class="mango-num mango-text-pass">'             + s.passed  + '</td>' +
            '<td class="mango-num mango-text-fail">'             + s.failed  + '</td>' +
            '<td class="mango-num mango-text-skip">'             + s.skipped + '</td>' +
            '<td class="mango-progress-cell">' + makeProgressBar(s.rate, s.isPassing) + '</td>' +
            '<td class="mango-status">' + icon + ' ' + statusText + '</td>' +
        '</tr>';
    }).join('');

    return '<table class="mango-table">' +
        '<thead><tr>' +
            '<th>Suite 名称</th><th>总计</th><th>通过</th><th>失败</th>' +
            '<th>跳过</th><th>通过率</th><th>状态</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
    '</table>';
}

function renderStatsPane(data) {
    var solutions = (data && data.children) ? data.children : [];

    if (solutions.length === 0) {
        return '<div class="mango-empty-hint">' +
            '⚠️ 暂无统计数据。<br>' +
            '请确保测试中已调用 <code>allure.dynamic.epic / feature / story</code> 标签，' +
            '并且 behaviors-plugin 已启用。' +
        '</div>';
    }

    var html = '<h1 class="mango-main-title">📊 Mango 测试统计看板</h1>';

    solutions.forEach(function (solution) {
        var ss = computeStats(solution);
        html += '<div class="mango-card">' +
            '<div class="mango-card-header mango-level-solution">' +
                '<span class="mango-header-label">📁 ' + (solution.name || 'Solution') + '</span>' +
                '<div class="mango-header-stats">' +
                    '<span class="mango-badge mango-badge-total">总 ' + ss.total  + '</span>' +
                    '<span class="mango-badge mango-badge-pass">✔ '   + ss.passed + '</span>' +
                    '<span class="mango-badge mango-badge-fail">✘ '   + ss.failed + '</span>' +
                    makeProgressBar(ss.rate, ss.isPassing) +
                '</div>' +
            '</div>' +
            '<div class="mango-card-body">';

        (solution.children || []).forEach(function (scene) {
            var ds = computeStats(scene);
            html += '<div class="mango-scene-block">' +
                '<div class="mango-scene-header mango-level-scene">' +
                    '<span class="mango-header-label">🔖 ' + (scene.name || 'Define') + '</span>' +
                    '<div class="mango-header-stats">' +
                        '<span class="mango-badge mango-badge-total">总 ' + ds.total  + '</span>' +
                        '<span class="mango-badge mango-badge-pass">✔ '   + ds.passed + '</span>' +
                        '<span class="mango-badge mango-badge-fail">✘ '   + ds.failed + '</span>' +
                        makeProgressBar(ds.rate, ds.isPassing) +
                    '</div>' +
                '</div>' +
                renderSuiteTable(scene.children || []) +
            '</div>';
        });

        html += '</div></div>';
    });

    return html;
}

// ====================================================================
// ─── 工具函数：Suite 报告树渲染 ─────────────────────────────────────
// ====================================================================

/**
 * 将 manifest.reports 数组按 define → suite 两级聚合成嵌套 Map：
 *   { defineName: { suiteName: [reportEntry, ...] } }
 */
function groupReports(reports) {
    var tree = {};
    (reports || []).forEach(function (r) {
        if (!tree[r.define]) { tree[r.define] = {}; }
        if (!tree[r.define][r.suite]) { tree[r.define][r.suite] = []; }
        tree[r.define][r.suite].push(r);
    });
    return tree;
}

/**
 * 根据聚合树生成左侧导航 HTML。
 * 每条报告链接携带 data-file 属性，供点击事件读取。
 */
function renderReportsTree(tree) {
    var html = '';
    Object.keys(tree).sort().forEach(function (defineName) {
        html += '<div class="mango-tree-define">' +
                '<div class="mango-tree-define-header" onclick="mangoToggleNode(this)">' +
                    '<span class="mango-tree-arrow">▼</span>' +
                    '<span class="mango-tree-label">📁 ' + defineName + '</span>' +
                '</div>' +
                '<div class="mango-tree-define-body">';

        Object.keys(tree[defineName]).sort().forEach(function (suiteName) {
            html += '<div class="mango-tree-suite">' +
                    '<div class="mango-tree-suite-header" onclick="mangoToggleNode(this)">' +
                        '<span class="mango-tree-arrow">▼</span>' +
                        '<span class="mango-tree-label">🗂 ' + suiteName + '</span>' +
                    '</div>' +
                    '<div class="mango-tree-suite-body">';

            tree[defineName][suiteName].forEach(function (r) {
                var typeIcon = r.type === 'delay' ? '⏱' : (r.type === 'asr_accuracy' ? '🎯' : '🌐');
                html += '<div class="mango-tree-report" data-file="' + r.file + '"' +
                            ' onclick="mangoOpenReport(this)">' +
                            typeIcon + ' ' + r.title +
                        '</div>';
            });

            html += '</div></div>';  // suite-body / suite
        });

        html += '</div></div>';  // define-body / define
    });
    return html || '<div class="mango-tree-empty">暂无 Suite 报告</div>';
}

/** 折叠 / 展开树节点 */
function mangoToggleNode(headerEl) {
    var body = headerEl.nextElementSibling;
    var arrow = headerEl.querySelector('.mango-tree-arrow');
    if (!body) return;
    var collapsed = body.style.display === 'none';
    body.style.display = collapsed ? '' : 'none';
    if (arrow) arrow.textContent = collapsed ? '▼' : '▶';
}

/**
 * 切换子 Tab（全局函数，供按钮 onclick 调用）
 * @param {HTMLElement} btn      被点击的按钮
 * @param {string}      targetId 要显示的面板 ID
 */
function mangoSwitchTab(btn, targetId) {
    // 向上找到 .mango-container 作为查找边界
    var container = btn.closest ? btn.closest('.mango-container') : (function() {
        var el = btn;
        while (el && !(el.className && el.className.indexOf('mango-container') >= 0)) {
            el = el.parentElement;
        }
        return el;
    })();

    // 更新按钮高亮
    if (container) {
        var btns = container.querySelectorAll('.mango-subtab');
        for (var i = 0; i < btns.length; i++) {
            btns[i].classList.remove('mango-subtab-active');
        }
    }
    btn.classList.add('mango-subtab-active');

    // 隐藏所有面板，显示目标面板
    if (container) {
        var panes = container.querySelectorAll('.mango-pane');
        for (var j = 0; j < panes.length; j++) {
            panes[j].style.display = 'none';
        }
    }
    var target = document.getElementById(targetId);
    if (target) {
        target.style.display = '';
    }
}

/**
 * 打开报告链接（全局函数，供报告条目 onclick 调用）
 * @param {HTMLElement} item 被点击的报告条目
 */
function mangoOpenReport(item) {
    var relFile = item.getAttribute('data-file');
    if (!relFile) return;

    // 高亮选中
    var tree = item.closest ? item.closest('.mango-reports-tree') : null;
    if (tree) {
        var reports = tree.querySelectorAll('.mango-tree-report');
        for (var i = 0; i < reports.length; i++) {
            reports[i].classList.remove('mango-tree-report-active');
        }
    }
    item.classList.add('mango-tree-report-active');

    // 在 iframe 中显示报告
    var hint   = document.getElementById('mango-iframe-hint');
    var iframe = document.getElementById('mango-report-iframe');
    if (hint)   { hint.style.display = 'none'; }
    if (iframe) {
        iframe.src          = 'mango-reports/' + relFile;
        iframe.style.display = '';
    }
}

// ====================================================================
// ─── Backbone 视图 ──────────────────────────────────────────────────
// ====================================================================

var MangoTabModel = Backbone.Model.extend({
    url: 'data/behaviors.json'
});

class MangoLayout extends allure.components.AppLayout {
    initialize() {
        this.model = new MangoTabModel();
    }
    loadData() {
        return this.model.fetch();
    }
    getContentView() {
        return new MangoTabView({ model: this.model });
    }
}

var MangoTabView = Backbone.Marionette.View.extend({

    // ── 模板：初始骨架，statistics 内容在 serializeData 中填入 ──────
    template: function (data) {
        return (
            '<div class="mango-container">' +
                // ── 子 Tab 导航 ──────────────────────────────────────
                '<div class="mango-subtab-nav">' +
                    '<button class="mango-subtab mango-subtab-active"' +
                        ' onclick="mangoSwitchTab(this,\'' + SUBTAB_STATS + '\')">📊 测试统计</button>' +
                    '<button class="mango-subtab"' +
                        ' onclick="mangoSwitchTab(this,\'' + SUBTAB_REPORTS + '\')">📄 Suite 报告</button>' +
                '</div>' +
                // ── 测试统计 Pane ────────────────────────────────────
                '<div id="' + SUBTAB_STATS + '" class="mango-pane mango-pane-active">' +
                    renderStatsPane(data) +
                '</div>' +
                // ── Suite 报告 Pane ──────────────────────────────────
                '<div id="' + SUBTAB_REPORTS + '" class="mango-pane" style="display:none">' +
                    '<div class="mango-reports-layout">' +
                        '<div class="mango-reports-tree" id="mango-reports-tree">' +
                            '<div class="mango-tree-loading">⏳ 加载报告目录...</div>' +
                        '</div>' +
                        '<div class="mango-reports-content">' +
                            '<div class="mango-iframe-hint" id="mango-iframe-hint">' +
                                '👈 请从左侧选择一份报告查看' +
                            '</div>' +
                            '<iframe id="mango-report-iframe" class="mango-report-iframe" src="about:blank" style="display:none"></iframe>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>'
        );
    },

    serializeData: function () {
        return this.model.toJSON();
    },

    // ── 渲染完成后加载 manifest（事件绑定全部通过 onclick 内联，不依赖 Backbone events hash）
    onRender: function () {
        var self = this;
        fetch('mango-reports/manifest.json')
            .then(function (res) {
                if (!res.ok) { throw new Error('HTTP ' + res.status); }
                return res.json();
            })
            .then(function (manifest) {
                var tree    = groupReports(manifest.reports || []);
                var treeHtml = renderReportsTree(tree);
                self.$el.find('#mango-reports-tree').html(treeHtml);
            })
            .catch(function () {
                self.$el.find('#mango-reports-tree').html(
                    '<div class="mango-tree-empty">暂无 Suite 报告<br><small>（manifest.json 不存在或尚未运行测试）</small></div>'
                );
            });
    }
});

// ====================================================================
// 注册 Tab
// ====================================================================
allure.api.addTab('mango', {
    title: 'Mango 统计',
    icon: 'fa fa-bar-chart',
    route: 'mango',
    onEnter: (function () {
        return new MangoLayout();
    })
});
