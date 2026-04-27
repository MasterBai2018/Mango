(function () {
    // 1. 定义数据模型，指向我们稍后生成的 json 文件
    var SuiteModel = Backbone.Model.extend({
        url: 'data/custom_suite_summary.json'
    });

    // 2. 定义 Tab 视图
    var SuiteSummaryView = allure.components.AppView.extend({
        initialize: function () {
            this.model = new SuiteModel();
            // 获取数据后触发渲染
            this.model.fetch().then(this.render.bind(this));
        },
        template: function (data) {
            // 这里建议使用 Handlebars 渲染，或者简单的拼接 HTML
            // data 即 custom_suite_summary.json 的内容
            var html = '<div class="suite-dashboard"><h1>Suite 运行状态汇总</h1>';
            html += '<table class="kpi-table"><thead><tr><th>Suite</th><th>通过率</th><th>附件</th></tr></thead>';
            
            data.suites.forEach(function(item) {
                var statusClass = parseFloat(item.rate) >= 90 ? 'pass' : 'fail';
                html += '<tr class="' + statusClass + '">';
                html += '<td>' + item.name + '</td>';
                html += '<td>' + item.rate + '%</td>';
                html += '<td><a href="data/attachments/' + item.fileId + '" target="_blank">查看 ASR 日志</a></td>';
                html += '</tr>';
            });
            
            html += '</table></div>';
            return html;
        }
    });

    // 3. 注册 Tab
    allure.api.addTab('suite_kpi', {
        title: 'Suite 看板',
        icon: 'fa fa-tachometer',
        route: 'suite_kpi',
        onEnter: (function () {
            return new SuiteSummaryView();
        })
    });
})();