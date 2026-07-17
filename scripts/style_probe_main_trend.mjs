import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/29266/Desktop/主力趋势.xlsx";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const probes = [
  "资金面趋势!H3",   // 内资+
  "资金面趋势!U3",   // 外资+ 内资+
  "资金面趋势!R3",   // 内资-
  "资金面趋势!BI3",  // 外资- 内资-
  "资金面趋势!O4",   // 外资- 内资- 家人+
  "资金面趋势!EO3:EO55",
];

for (const range of probes) {
  const out = await workbook.inspect({
    kind: "table,computedStyle",
    range,
    include: "values,computedStyle",
    tableMaxRows: 4,
    tableMaxCols: 4,
    maxChars: 5000,
  });
  console.log(`RANGE ${range}`);
  console.log(out.ndjson);
}
