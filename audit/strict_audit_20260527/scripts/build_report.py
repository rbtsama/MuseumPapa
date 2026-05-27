from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "audit" / "strict_audit_20260527"
OUT_DATA = OUT / "outputs"


def load(name: str):
    return json.loads((OUT_DATA / name).read_text(encoding="utf-8"))


def fmt_assabet_issue(row: dict) -> str:
    if row["expected_verdict"] == "accepted" and row["probe_verdict"] == "rejected_resident":
        kind = "面板偏宽"
        claim = "结构化数据判定为可被同网络非本镇卡预订"
        reality = f"实测用 {row['prober_card']} 卡在卡校验即被拒"
    else:
        kind = "面板偏严"
        claim = "结构化数据判定为需要本馆卡/本镇资格"
        reality = f"实测用 {row['prober_card']} 卡可通过卡校验"
    return (
        f"| {kind} | {row['network']} | {row['library_id']} | {row['attraction_slug']} | "
        f"{claim} | {reality} | [源页]({row['source_url']}) |"
    )


def main() -> None:
    assabet = load("assabet_audit_results.json")
    bpl = load("bpl_public_results.json")
    retry = load("playwright_retry_results.json")

    assabet_conclusive = [r for r in assabet if r["status"] == "conclusive"]
    assabet_mismatches = [r for r in assabet if "Structured data expects" in (r["issue"] or "")]
    retry_by_key = {(r["library_id"], r["attraction_rawslug"], r["card_label"]): r for r in retry}

    assabet_blockers = [
        r for r in assabet
        if r["status"] != "conclusive" or ("WinError 10054" in (r["issue"] or "")) or ("UNEXPECTED_EOF" in (r["issue"] or ""))
    ]
    unresolved_blockers = []
    resolved_blockers = []
    for row in assabet_blockers:
        key = (row["library_id"], row["attraction_rawslug"], row["prober_card"])
        rr = retry_by_key.get(key)
        if rr and rr["verdict"] in {"accepted", "rejected_resident"}:
            resolved_blockers.append((row, rr))
        else:
            unresolved_blockers.append((row, rr))

    bpl_concrete = []
    for r in bpl:
        issues = []
        if "Structured pass_form is not digital_email" in (r["issue"] or ""):
            issues.append("`pass_form` 与官网公开页冲突：官网明确写 `Digital (downloadable via email)`。")
        if "404 page" in (r["issue"] or ""):
            issues.append("`source_url` 直接返回 404。")
        if issues:
            bpl_concrete.append((r, issues))

    report = []
    report.append("# Museum Papa 严格审计报告（第一轮）")
    report.append("")
    report.append("## 范围与方法")
    report.append("")
    report.append("- 审计日期：2026-05-27")
    report.append("- 审计范围：`admin/panel.html` 对应的后台数据与 panel 展示；忽略用户端。")
    report.append("- 本轮目标：先记录问题数据点，不展开修复方案。")
    report.append("- 忽略项：库存真假、具体日期可用性；日期仅被当作进入真实预约流程的通道。")
    report.append("- 真实验证方式：")
    report.append("  - `Assabet`：直接访问官网预约页，使用现有 5 张卡中的同网络跨镇卡，打到真实卡校验步骤。")
    report.append("  - `BPL / LibCal`：访问官网公开页，并尝试进入预订入口；因仓库只提供条码、未提供 PIN，无法完成需要 `card + PIN` 的最后登录步。")
    report.append("")
    report.append("## 样本量")
    report.append("")
    report.append(f"- `Assabet` 抽样 {len(assabet)} 个数据点，其中 {len(assabet_conclusive)} 个拿到真实、明确的卡校验结论。")
    report.append(f"- 另外对 4 个阻塞点做了 Playwright 真人式复测，其中 3 个拿到了补充结论。")
    report.append(f"- `BPL / LibCal` 公开页核验 {len(bpl)} 个数据点。")
    report.append(f"- 总样本数：{len(assabet) + len(bpl)}。")
    report.append("")
    report.append("## 本轮确认存在问题的数据点")
    report.append("")
    report.append("### A. Assabet：结构化可预订权限与官网实测不一致")
    report.append("")
    report.append("| 类型 | Network | Library | Attraction | 面板/结构化数据主张 | 官网实测 | 证据 |")
    report.append("|---|---|---|---|---|---|---|")
    for row in assabet_mismatches:
        report.append(fmt_assabet_issue(row))
    report.append("")
    report.append(f"Assabet 这一类一共确认了 {len(assabet_mismatches)} 个问题数据点。")
    report.append("")
    report.append("### B. BPL / LibCal：公开页即可确认的问题")
    report.append("")
    report.append("| Library | Attraction | 问题 | 证据 |")
    report.append("|---|---|---|---|")
    for row, issues in bpl_concrete:
        report.append(
            f"| {row['library_id']} | {row['attraction_slug']} | {' '.join(issues)} | [源页]({row['source_url']}) |"
        )
    report.append("")
    report.append(f"BPL 这一类当前确认了 {len(bpl_concrete)} 个公开页即可落锤的问题数据点。")
    report.append("")
    report.append("### C. 阻塞复测后新增确认")
    report.append("")
    report.append("| Library | Attraction | Playwright 复测结果 | 处理方式 |")
    report.append("|---|---|---|---|")
    for base, rr in resolved_blockers:
        if rr["verdict"] == "accepted":
            decision = "解除阻塞，但不记为问题数据点。"
        elif rr["verdict"] == "rejected_resident":
            decision = "解除阻塞；与当前结构化结论一致，不新增问题点。"
        else:
            decision = "解除阻塞。"
        report.append(
            f"| {base['library_id']} | {base['attraction_slug']} | `{rr['verdict']}` | {decision} |"
        )
    report.append("")
    report.append("## 阻塞与未落锤项")
    report.append("")
    report.append("### 1. 需要复测但暂不记为数据错误")
    report.append("")
    for row, rr in unresolved_blockers:
        extra = ""
        if rr:
            extra = f" Playwright 复测结果：`{rr['verdict']}`。"
        report.append(f"- `{row['library_id']} / {row['attraction_slug']}`：{row['issue'] or row['status']}.{extra}")
    report.append("")
    report.append("### 2. BPL / LibCal 的最终预订权限仍未完全落锤")
    report.append("")
    report.append("- 真实官网已经验证到：BPL 的部分数字 pass 会跳到 `BPL LibCal Login`，明确要求 `library card number + PIN`。")
    report.append("- 当前仓库只给了条码，没有 PIN，因此本轮不能诚实地声称“已经验证到最后一步”。")
    report.append("- 这不记为数据错误，只记为凭证阻塞。")
    report.append("")
    report.append("## 联盟关系观察")
    report.append("")
    report.append("- 本轮没有拿到足够证据证明 `library ↔ alliance/network` 映射本身有系统性错误。")
    report.append("- 相反，`Minuteman / NOBLE / MVLC` 中大量 pass 都能用同网络跨镇卡打到真实卡校验，说明网络识别总体是活的。")
    report.append("- 当前更像是“同一 network 内，不同 library 对具体 pass 的可预订权限差异很大，而结构化数据把它们放宽了”，尤其集中在 `MVLC`。")
    report.append("")
    report.append("## 重点结论")
    report.append("")
    report.append(f"- 本轮总共确认 {len(assabet_mismatches) + len(bpl_concrete)} 个问题数据点。")
    report.append("- 其中最显著的问题簇在 `MVLC`：多家 library 的多个 pass，结构化数据判定“同网络非本镇卡可订”，但官网真实卡校验直接拒绝。")
    report.append("- `North Reading` 出现反向问题：结构化数据把多个 pass 判成需要本馆卡，但实测同网络跨镇卡可以通过。")
    report.append("- `BPL` 至少有 2 个 pass 的 `pass_form` 与公开页矛盾，另有 1 个 `source_url` 已经 404。")
    report.append("")

    out_path = OUT / "strict_audit_report_20260527.md"
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote report to {out_path}")


if __name__ == "__main__":
    main()
