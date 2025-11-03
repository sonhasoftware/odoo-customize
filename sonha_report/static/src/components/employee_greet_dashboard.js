/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { onWillStart, onMounted, useRef, useState } from "@odoo/owl";

export class EmployeeInOutDashboard extends owl.Component {
    setup() {
        this.orm = useService("orm");
        this.user = useService("user");

        this.state = useState({
            company_id: null,
            year: new Date().getFullYear(),
            companies: [],
            data: [],
            contract_data: [],
            amount_data: [],
        });

        // Chart references
        this.barChartRef = useRef("barChart");
        this.pieChartRef = useRef("pieChart");
        this.totalEmployeeChartRef = useRef("totalEmployeeChart");

        // Chart objects
        this.barChart = null;
        this.pieChart = null;
        this.totalEmployeeChart = null;

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
            await loadJS("https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0/dist/chartjs-plugin-datalabels.min.js");

            this.state.companies = await this.getCompanies();
            this.state.company_id =
                this.state.companies.find((c) => c.is_default)?.id ||
                this.state.companies[0]?.id;

            await this.loadAllData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadAllData() {
        this.state.data = await this.getInOutData();
        this.state.contract_data = await this.getContractData();
        this.state.amount_data = await this.getAmountData();
    }

    async getCompanies() {
        const response = await fetch("/get_user_companies");
        return await response.json();
    }

    async getInOutData() {
        const params = new URLSearchParams({
            company_id: this.state.company_id,
            year: this.state.year,
        });
        const response = await fetch(`/get_employee_inout_data?${params.toString()}`);
        return await response.json();
    }

    async getContractData() {
        const params = new URLSearchParams({
            company_id: this.state.company_id,
        });
        const response = await fetch(`/get_employee_contract_data?${params.toString()}`);
        return await response.json();
    }

    async getAmountData() {
        const params = new URLSearchParams({
            company_id: this.state.company_id,
            year: this.state.year,
        });
        const response = await fetch(`/get_amount_employee_data?${params.toString()}`);
        return await response.json();
    }

    async applyFilters() {
        await this.loadAllData();
        this.renderCharts();
    }

    renderCharts() {
        this.renderBarChart();
        this.renderPieChart();
        this.renderTotalEmployeeChart();
    }

    // -------------------- BIỂU ĐỒ NHÂN VIÊN VÀO/RA --------------------
    renderBarChart() {
        if (!window.Chart || !this.barChartRef.el) return;
        if (this.barChart) this.barChart.destroy();

        const labels = this.state.data.map((item) => item.month);
        const onboard = this.state.data.map((item) => item.onboard_count);
        const quit = this.state.data.map((item) => item.quit_count);

        this.barChart = new Chart(this.barChartRef.el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Nhân viên vào",
                        data: onboard,
                        backgroundColor: "rgba(75, 192, 192, 0.8)",
                    },
                    {
                        label: "Nhân viên nghỉ",
                        data: quit,
                        backgroundColor: "rgba(255, 99, 132, 0.8)",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    datalabels: {
                        anchor: "end",
                        align: "top",
                        formatter: (value) => (value > 0 ? value : ""),
                        color: "#333",
                        font: { weight: "bold" },
                    },
                    legend: { position: "bottom" },
                    title: {
                        display: true,
                        text: `Thống kê nhân viên vào/ra (${this.state.year})`,
                    },
                },
                scales: {
                    x: { title: { display: true, text: "Tháng" } },
                    y: { beginAtZero: true, title: { display: true, text: "Số nhân viên" } },
                },
            },
            plugins: [ChartDataLabels],
        });
    }

    // -------------------- BIỂU ĐỒ TỶ LỆ LOẠI HỢP ĐỒNG --------------------
    renderPieChart() {
        if (!window.Chart || !this.pieChartRef.el) return;
        if (this.pieChart) this.pieChart.destroy();

        const labels = this.state.contract_data.map((item) => item.contract_type);
        const data = this.state.contract_data.map((item) => item.count);

        // Random màu ổn định theo tên
        function colorFromString(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            const r = (hash >> 16) & 255;
            const g = (hash >> 8) & 255;
            const b = hash & 255;
            return `rgba(${Math.abs(r)}, ${Math.abs(g)}, ${Math.abs(b)}, 0.8)`;
        }

        this.pieChart = new Chart(this.pieChartRef.el, {
            type: "pie",
            data: {
                labels,
                datasets: [
                    {
                        label: "Hợp đồng",
                        data,
                        backgroundColor: labels.map((l) => colorFromString(l)),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                    title: {
                        display: true,
                        text: "Tỷ lệ nhân viên theo loại hợp đồng",
                    },
                },
            },
        });
    }

    // -------------------- BIỂU ĐỒ TỔNG SỐ NHÂN VIÊN --------------------
    renderTotalEmployeeChart() {
        if (!window.Chart || !this.totalEmployeeChartRef.el) return;
        if (this.totalEmployeeChart) this.totalEmployeeChart.destroy();

        const labels = this.state.amount_data.map((item) => item.month);
        const counts = this.state.amount_data.map((item) => item.count);

        this.totalEmployeeChart = new Chart(this.totalEmployeeChartRef.el, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Số nhân viên",
                        data: counts,
                        backgroundColor: "rgba(54, 162, 235, 0.7)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: {
                        display: true,
                        text: `Tổng số nhân viên theo tháng (${this.state.year})`,
                    },
                },
                scales: {
                    x: { title: { display: true, text: "Tháng" } },
                    y: { beginAtZero: true, title: { display: true, text: "Số nhân viên" } },
                },
            },
        });
    }
}

EmployeeInOutDashboard.template = "employee_inout_dashboard_template";

registry.category("actions").add("employee.inout_dashboard", EmployeeInOutDashboard);
