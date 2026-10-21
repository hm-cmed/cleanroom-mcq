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
  // 助成を受けた場合はここに書く（例：{ funder: "○○財団", title: "", number: "" }）
  grants: [],
  license: {
    code: "MIT License",
    content: "CC BY 4.0"
  }
};
