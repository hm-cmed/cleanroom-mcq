/*
 * 設定（このファイルだけ書き換えれば、表示がまとめて変わります）
 */
window.MCQ_CONFIG = {
  appName: "クリーンルーム5択ドリル",
  subtitle: "消化器",
  version: "0.1.0",
  developer: "三原 弘（札幌医科大学 医療人育成センター）",
  repository: "https://github.com/hm-cmed/cleanroom-mcq",
  factsRepository: "https://github.com/hm-cmed/cleanroom-facts",
  // 監修前（status: draft）の問題も出題するか。監修済みの問題がそろったら false にする
  showDrafts: true,
  // 学年別の「おまかせ出題」の配分。core は、モデル・コア・カリキュラムに沿って選ぶ割合（0〜1）。
  // 残り（1 - core）は医師国家試験ブループリントに沿って選ぶ。学年や割合は自由に変えてよい。
  gradeProfiles: [
    { id: "1", label: "1年生", core: 1 },
    { id: "2", label: "2年生", core: 1 },
    { id: "3", label: "3年生", core: 1 },
    { id: "4", label: "4年生", core: 1 },
    { id: "5", label: "5年生", core: 0.5 },
    { id: "6", label: "6年生", core: 0 },
    { id: "pg", label: "卒業生・研修医", core: 0 }
  ],
  // 助成を受けた場合はここに書く（例：{ funder: "○○財団", title: "", number: "" }）
  grants: [],
  license: {
    code: "MIT License",
    content: "CC BY 4.0"
  }
};
