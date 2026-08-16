import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ENTITY_DIRS = ["projects", "actions", "weeks", "inbox", "reviews"];
const COLORS = {
  navy: "#172033",
  blue: "#365BCE",
  blueSoft: "#EAF0FF",
  ink: "#1D2633",
  muted: "#667085",
  line: "#D9DEE8",
  paper: "#F7F8FA",
  green: "#16734B",
  amber: "#A45C00",
};

const args = {};
for (let index = 2; index < process.argv.length; index += 1) {
  const item = process.argv[index];
  if (item.startsWith("--")) args[item.slice(2)] = process.argv[index + 1] && !process.argv[index + 1].startsWith("--") ? process.argv[++index] : true;
}
const dataDir = path.resolve(ROOT, args["data-dir"] || process.env.WEEKLOOM_DATA_DIR || ".weekloom-data");
const outputPath = path.resolve(ROOT, args.output || "exports/Weekloom.xlsx");

async function readEntity(entity) {
  const directory = path.join(dataDir, entity);
  try {
    const names = (await fs.readdir(directory)).filter((name) => name.endsWith(".json")).sort();
    return Promise.all(names.map(async (name) => JSON.parse(await fs.readFile(path.join(directory, name), "utf8"))));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function dateValue(value) {
  return value ? new Date(`${value}T00:00:00`) : null;
}

function styleTitle(range) {
  range.format = { fill: COLORS.navy, font: { bold: true, color: "#FFFFFF", size: 18 }, horizontalAlignment: "left", verticalAlignment: "center" };
  range.format.rowHeight = 30;
}

function styleSection(range) {
  range.format = { fill: COLORS.blueSoft, font: { bold: true, color: COLORS.ink, size: 12 }, verticalAlignment: "center" };
  range.format.rowHeight = 22;
}

function styleHeader(range) {
  range.format = { fill: COLORS.navy, font: { bold: true, color: "#FFFFFF" }, wrapText: true, verticalAlignment: "center" };
  range.format.rowHeight = 24;
  range.format.borders = { preset: "all", style: "thin", color: COLORS.line };
}

function styleBody(range) {
  range.format = { font: { color: COLORS.ink }, verticalAlignment: "center", wrapText: true };
  range.format.borders = { preset: "all", style: "thin", color: COLORS.line };
}

function setWidths(sheet, widths) {
  for (const [column, width] of Object.entries(widths)) sheet.getRange(`${column}:${column}`).format.columnWidth = width;
}

function writeTable(sheet, startCell, headers, rows) {
  const startMatch = startCell.match(/^([A-Z]+)(\d+)$/);
  const startColumn = startMatch[1];
  const startRow = Number(startMatch[2]);
  const endColumn = String.fromCharCode(startColumn.charCodeAt(0) + headers.length - 1);
  const endRow = startRow + Math.max(rows.length, 1);
  sheet.getRange(`${startColumn}${startRow}:${endColumn}${startRow}`).values = [headers];
  styleHeader(sheet.getRange(`${startColumn}${startRow}:${endColumn}${startRow}`));
  if (rows.length) {
    sheet.getRange(`${startColumn}${startRow + 1}:${endColumn}${endRow}`).values = rows;
    styleBody(sheet.getRange(`${startColumn}${startRow + 1}:${endColumn}${endRow}`));
  }
  return { startRow, endRow, startColumn, endColumn };
}

function lineList(value) {
  return Array.isArray(value) ? value.join("；") : "";
}

const [projects, actions, weeks, inbox, reviews] = await Promise.all(ENTITY_DIRS.map(readEntity));
const currentWeek = [...weeks].sort((a, b) => String(b.week_start).localeCompare(String(a.week_start)))[0] || null;
const currentActions = currentWeek ? actions.filter((action) => action.week_id === currentWeek.id) : actions;
const currentReview = currentWeek ? reviews.find((review) => review.week_id === currentWeek.id) : null;
const projectById = new Map(projects.map((project) => [project.id, project]));

const workbook = Workbook.create();
const dashboard = workbook.worksheets.add("Dashboard");
const projectsSheet = workbook.worksheets.add("Projects");
const actionsSheet = workbook.worksheets.add("Actions");
const weeklySheet = workbook.worksheets.add("Weekly Log");
for (const sheet of [dashboard, projectsSheet, actionsSheet, weeklySheet]) sheet.showGridLines = false;

dashboard.mergeCells("A1:K1");
dashboard.getRange("A1").values = [["Weekloom · 周织 Dashboard"]];
styleTitle(dashboard.getRange("A1:K1"));
dashboard.getRange("A2:K2").merge();
dashboard.getRange("A2").values = [[currentWeek ? `${currentWeek.id} · ${currentWeek.week_start} — ${currentWeek.week_end}` : "尚未建立周计划"]];
dashboard.getRange("A2:K2").format = { font: { color: COLORS.muted, italic: true }, fill: COLORS.paper };

dashboard.getRange("A4:B4").values = [["本周概览", ""]];
styleSection(dashboard.getRange("A4:B4"));
dashboard.getRange("A5:B8").values = [
  ["当前周", currentWeek?.id || "—"],
  ["活跃项目", null],
  ["行动完成", null],
  ["开放 Inbox", null],
];
dashboard.getRange("B6").formulas = [["=COUNTIF('Projects'!$E$2:$E$100,\"active\")"]];
dashboard.getRange("B7").formulas = [["=COUNTIF('Actions'!$H$2:$H$100,\"done\")&\"/\"&COUNTA('Actions'!$A$2:$A$100)"]];
dashboard.getRange("B8").formulas = [["=COUNTIF('Actions'!$H$2:$H$100,\"todo\")"]];
styleBody(dashboard.getRange("A5:B8"));
dashboard.getRange("A5:A8").format.font = { bold: true, color: COLORS.muted };
dashboard.getRange("B5:B8").format.font = { bold: true, color: COLORS.ink, size: 14 };

dashboard.getRange("A10:E10").values = [["本周核心成果", "", "", "", ""]];
dashboard.mergeCells("A10:E10");
styleSection(dashboard.getRange("A10:E10"));
const outcomes = (currentWeek?.core_outcomes || []).map((item) => [item]);
writeTable(dashboard, "A11", ["成果"], outcomes.length ? outcomes : [["暂无核心成果"]]);

dashboard.getRange("A17:E17").values = [["需要关注的项目", "", "", "", ""]];
dashboard.mergeCells("A17:E17");
styleSection(dashboard.getRange("A17:E17"));
const attentionProjects = projects.filter((project) => project.status === "waiting" || project.status === "paused" || project.progress < 25);
const attentionRows = (attentionProjects.length ? attentionProjects : [{ name: "暂无异常项目", status: "—", progress: 0, next_action_id: "—", blocked_reason: "—" }]).map((project) => [
  project.name, project.status, project.progress / 100, project.next_action_id || "—", project.blocked_reason || "—",
]);
const attentionTable = writeTable(dashboard, "A18", ["项目", "状态", "进度", "下一步 ID", "阻碍/备注"], attentionRows);
dashboard.getRange(`C${attentionTable.startRow + 1}:C${attentionTable.endRow}`).format.numberFormat = "0%";

dashboard.getRange("J4:K4").values = [["行动状态", "数量"]];
styleHeader(dashboard.getRange("J4:K4"));
const statusRows = [["待办", "todo"], ["进行中", "doing"], ["已完成", "done"], ["放弃", "dropped"]];
dashboard.getRange("J5:J8").values = statusRows.map(([label]) => [label]);
dashboard.getRange("K5:K8").formulas = statusRows.map(([, value]) => [`=COUNTIF('Actions'!$H$2:$H$100,\"${value}\")`]);
styleBody(dashboard.getRange("J5:K8"));
const statusChart = dashboard.charts.add("bar", dashboard.getRange("J4:K8"));
statusChart.setPosition("D4", "I15");
statusChart.title = "本周行动状态";
statusChart.hasLegend = false;
statusChart.xAxis = { axisType: "textAxis" };
statusChart.yAxis = { numberFormatCode: "0" };

dashboard.getRange("A27:E27").values = [["复盘摘要", "", "", "", ""]];
dashboard.mergeCells("A27:E27");
styleSection(dashboard.getRange("A27:E27"));
const reviewRows = currentReview ? [
  ["完成与收获", lineList(currentReview.wins)],
  ["未完成", lineList(currentReview.unfinished)],
  ["阻碍", lineList(currentReview.blockers)],
  ["下周重点", lineList(currentReview.next_week_focus)],
] : [["状态", "本周尚未填写复盘"]];
writeTable(dashboard, "A28", ["项目", "内容"], reviewRows);
dashboard.getRange("B29:E40").format.wrapText = true;
setWidths(dashboard, { A: 24, B: 22, C: 12, D: 22, E: 34, F: 3, G: 3, H: 3, I: 3, J: 14, K: 10 });
dashboard.freezePanes.freezeRows(2);

const projectRows = projects.map((project) => [
  project.id, project.name, project.category, project.progress / 100, project.status, project.goal, dateValue(project.target_date), project.next_action_id || "", project.tags.join(", "), dateValue(project.updated_at?.slice(0, 10)),
]);
writeTable(projectsSheet, "A1", ["ID", "项目", "类别", "进度", "状态", "目标", "截止日期", "下一步 ID", "标签", "更新时间"], projectRows);
if (projectRows.length) projectsSheet.getRange(`D2:D${projectRows.length + 1}`).format.numberFormat = "0%";
if (projectRows.length) { projectsSheet.getRange(`G2:G${projectRows.length + 1}`).format.numberFormat = "yyyy-mm-dd"; projectsSheet.getRange(`J2:J${projectRows.length + 1}`).format.numberFormat = "yyyy-mm-dd"; }
if (projectRows.length) {
  const lastProjectRow = projectRows.length + 1;
  projectsSheet.getRange(`E2:E${lastProjectRow}`).dataValidation = { rule: { type: "list", values: ["active", "waiting", "paused", "completed", "archived"] } };
  projectsSheet.getRange(`C2:C${lastProjectRow}`).dataValidation = { rule: { type: "list", values: ["work", "personal_project", "personal_life", "interest_learning"] } };
}
setWidths(projectsSheet, { A: 24, B: 28, C: 20, D: 10, E: 14, F: 34, G: 14, H: 24, I: 20, J: 16 });
projectsSheet.freezePanes.freezeRows(1);

const actionRows = actions.map((action) => [
  action.id, action.title, action.project_id || "", action.week_id || "", action.category, action.priority, action.weekly_role, action.status, dateValue(action.due_date), action.estimate_minutes, action.is_next_action ? "是" : "", action.tags.join(", "), action.notes, dateValue(action.updated_at?.slice(0, 10)),
]);
writeTable(actionsSheet, "A1", ["ID", "行动", "项目 ID", "周 ID", "类别", "优先级", "本周角色", "状态", "截止日期", "估计分钟", "下一步", "标签", "备注", "更新时间"], actionRows);
if (actionRows.length) { actionsSheet.getRange(`I2:I${actionRows.length + 1}`).format.numberFormat = "yyyy-mm-dd"; actionsSheet.getRange(`J2:J${actionRows.length + 1}`).format.numberFormat = "#,##0"; actionsSheet.getRange(`N2:N${actionRows.length + 1}`).format.numberFormat = "yyyy-mm-dd"; }
if (actionRows.length) {
  const lastActionRow = actionRows.length + 1;
  actionsSheet.getRange(`E2:E${lastActionRow}`).dataValidation = { rule: { type: "list", values: ["work", "personal_project", "personal_life", "interest_learning"] } };
  actionsSheet.getRange(`F2:F${lastActionRow}`).dataValidation = { rule: { type: "list", values: ["urgent", "high", "normal", "low"] } };
  actionsSheet.getRange(`G2:G${lastActionRow}`).dataValidation = { rule: { type: "list", values: ["focus", "planned", "candidate", "recurring"] } };
  actionsSheet.getRange(`H2:H${lastActionRow}`).dataValidation = { rule: { type: "list", values: ["todo", "doing", "done", "dropped"] } };
}
setWidths(actionsSheet, { A: 24, B: 36, C: 22, D: 12, E: 20, F: 12, G: 14, H: 12, I: 14, J: 12, K: 10, L: 20, M: 40, N: 16 });
actionsSheet.freezePanes.freezeRows(1);

const weeklyRows = weeks.map((week, index) => {
  const row = index + 2;
  return [week.id, dateValue(week.week_start), dateValue(week.week_end), week.status, week.theme, lineList(week.core_outcomes), null, null, null];
});
writeTable(weeklySheet, "A1", ["周 ID", "开始", "结束", "状态", "主题", "核心成果", "行动数", "完成数", "完成率"], weeklyRows);
if (weeklyRows.length) {
  const lastWeekRow = weeklyRows.length + 1;
  weeklySheet.getRange(`G2:G${lastWeekRow}`).formulas = weeklyRows.map((_, index) => [`=COUNTIF('Actions'!$D$2:$D$100,A${index + 2})`]);
  weeklySheet.getRange(`H2:H${lastWeekRow}`).formulas = weeklyRows.map((_, index) => [`=COUNTIFS('Actions'!$D$2:$D$100,A${index + 2},'Actions'!$H$2:$H$100,\"done\")`]);
  weeklySheet.getRange(`I2:I${lastWeekRow}`).formulas = weeklyRows.map((_, index) => [`=IF(G${index + 2}=0,0,H${index + 2}/G${index + 2})`]);
  weeklySheet.getRange(`B2:C${weeklyRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
  weeklySheet.getRange(`I2:I${weeklyRows.length + 1}`).format.numberFormat = "0%";
}
setWidths(weeklySheet, { A: 12, B: 14, C: 14, D: 14, E: 34, F: 44, G: 12, H: 12, I: 12 });
weeklySheet.freezePanes.freezeRows(1);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`Exported ${outputPath}`);
