import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/29266/Desktop/主力趋势.xlsx";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;

const targets = ["外资-\n内资-", "内资-\n外资-", "外资+\n内资+", "内资+\n外资+"];
const found = [];
for (let r = 0; r < values.length; r += 1) {
  for (let c = 0; c < values[r].length; c += 1) {
    const value = values[r][c];
    if (targets.includes(value)) {
      found.push({ row1: r + 1, col1: c + 1, value });
    }
  }
}
console.log(JSON.stringify(found.slice(0, 40), null, 2));
