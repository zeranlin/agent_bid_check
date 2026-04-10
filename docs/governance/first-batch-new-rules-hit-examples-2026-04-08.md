# 首批新规则命中输出示例归档（2026-04-08）

## 文档目的

本归档用于承接 `Task-G11`，为 `R-009 ~ R-012` 每条规则保留至少 1 份可追溯的命中输出示例，便于：

1. 后续业务复核
2. 注册表与任务单收口引用
3. 回归测试与治理台账核对

## R-009

- 规则标题：`将已取消或非强制资质资格作为资格条件，存在设置不当准入门槛风险`
- 来源样本：`regression_qualification_cancelled_or_non_mandatory_positive_011`
- 来源文件：`data/examples/v2_regression_eval_samples.json`
- 命中 failure code：`cancelled_or_non_mandatory_qualification_as_gate`

命中摘录：

```text
资格要求：投标人资格要求：投标人须具备省级主管部门已明令取消的行业资质证书。

门槛设置：未提供上述资质证书的，资格审查不通过。
```

## R-010

- 规则标题：`将已取消或非强制资质资格认证作为评审因素，存在评分设置不合规风险`
- 来源样本：`regression_scoring_cancelled_or_non_mandatory_positive_012`
- 来源文件：`data/examples/v2_regression_eval_samples.json`
- 命中 failure code：`cancelled_or_non_mandatory_credential_in_scoring`

命中摘录：

```text
评分要求：评分内容：投标人具备国务院已明令取消的资质、资格、认证的，每项加5分，最高加15分。

评分内容：评审委员会按得分情况进行档次评价。
```

## R-011

- 规则标题：`要求提供资质证照原件或电子证照纸质件，存在材料提交边界设置不当风险`
- 来源样本：`regression_original_or_paper_certificate_submission_positive_013`
- 来源文件：`data/examples/v2_regression_eval_samples.json`
- 命中 failure code：`original_or_paper_certificate_submission_gate`

命中摘录：

```text
材料要求：资格证明文件要求：投标人须提供资质证明文件原件、证照原件及电子证照纸质版。

门槛设置：未提交原件或纸质证照的，资格审查不通过。
```

## R-012

- 规则标题：`以供应商主体身份或地域条件设置准入门槛，存在限制竞争风险`
- 来源样本：`regression_supplier_identity_or_region_positive_014`
- 来源文件：`data/examples/v2_regression_eval_samples.json`
- 命中 failure code：`supplier_identity_or_region_limit_as_gate`

命中摘录：

```text
资格要求：投标人资格要求：供应商注册地须在本市，并在项目所在行政区域内设立分支机构或经营网点。

门槛设置：不满足上述要求的，资格审查不通过。
```
