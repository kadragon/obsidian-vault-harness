#!/usr/bin/env python3
"""SW사업 대가·기간 검증 — 결정론적 계산기.

fp/maint/sum : 「SW사업 대가산정 가이드」(2025년 개정판) 기준 대가 역산
period       : 「소프트웨어사업 계약 및 관리감독에 관한 지침」 별표 1
               (소프트웨어 개발사업의 적정 사업기간 산정 기준) 기준 개발기간 산정

기준값 출처: references/daega-baseline.md · references/legal-basis.md
"""

from __future__ import annotations

import argparse
import math
import sys

# --- 2025년 개정판 기준값 (개정 시 daega-baseline.md와 함께 갱신) -------------
FP_UNIT_PRICE = 605_784       # 기능점수당 단가(원)
SIZE_COEF_UNDER_500FP = 1.28  # 규모 보정계수 (500FP 미만 고정)
DEFAULT_PROFIT_RATE = 0.25    # 이윤 (개발원가의 25% 이내)
MAINT_RATE_MIN = 0.10         # 요율제 유지관리 요율 하한
MAINT_RATE_MAX = 0.15         # 요율제 유지관리 요율 상한
VAT_RATE = 0.1
GUIDE_SAMPLE_FP = 73          # 가이드 부록 예시(사용자앱 42 + 관리자앱 31)
GUIDE_VERSION = "2025년 개정판"

# --- 지침 별표 1: 1인 생산성 (FP/MM) — 규모 구간별 --------------------------
PRODUCTIVITY_BANDS = [
    (0, 1000, 19),
    (1000, 2000, 22),
    (2000, 3000, 24),
    (3000, float("inf"), 22),
]
SIMPLIFIED_REVIEW_LIMIT = 100_000_000  # 지침 §10②·대학 운영지침 §5③1호: 1억원


def positive_float(value: str) -> float:
    """0 이하를 argparse 단계에서 거른다 — 기간·인력 0은 ZeroDivisionError."""
    v = float(value)
    if v <= 0:
        raise argparse.ArgumentTypeError(f"0보다 커야 함: {value}")
    return v


def positive_int(value: str) -> int:
    v = int(value)
    if v <= 0:
        raise argparse.ArgumentTypeError(f"0보다 커야 함: {value}")
    return v


def supply_price(amount: float, vat_included: bool) -> float:
    """부가가치세를 제외한 공급가."""
    return amount / (1 + VAT_RATE) if vat_included else float(amount)


def won(v: float) -> str:
    return f"{round(v):,}원"


def size_coef_for(fp: float) -> float:
    """규모 보정계수. 500FP 미만은 1.28 고정."""
    if fp < 500:
        return SIZE_COEF_UNDER_500FP
    return 0.4057 * (math.log(fp) - 7.1978) ** 2 + 0.8878


def cmd_fp(args: argparse.Namespace) -> int:
    supply = supply_price(args.amount, args.vat_included)
    coef = args.size_coef * args.other_coef
    dev_cost_after = supply / (1 + args.profit_rate)   # 보정 후 개발원가
    dev_cost_before = dev_cost_after / coef            # 보정 전 개발원가
    fp = dev_cost_before / FP_UNIT_PRICE

    print(f"[기능점수 역산]  가이드 {GUIDE_VERSION} · FP당 단가 {FP_UNIT_PRICE:,}원")
    print(f"  계상 금액          {won(args.amount)} ({'VAT 포함' if args.vat_included else 'VAT 제외'})")
    print(f"  공급가             {won(supply)}")
    print(f"  이윤율             {args.profit_rate:.0%}  → 보정 후 개발원가 {won(dev_cost_after)}")
    print(f"  보정계수           규모 {args.size_coef} × 기타 {args.other_coef} = {coef:.4f}")
    print(f"  보정 전 개발원가   {won(dev_cost_before)}")
    print(f"  환산 기능점수      약 {fp:,.0f} FP")
    print()
    print(f"  참고: 가이드 부록 예시(사용자앱 + 관리자앱 2본) = {GUIDE_SAMPLE_FP} FP")
    if fp < GUIDE_SAMPLE_FP:
        print("  ** 부록 예시보다 작음 — 과업 요구사항 건수와 나란히 제시할 것")
    if args.size_coef == SIZE_COEF_UNDER_500FP and fp >= 500:
        print("  ** 환산 FP가 500 이상 — 규모 보정계수를 산식으로 재계산할 것"
              f" (해당 FP 기준 {size_coef_for(fp):.4f})")
    print()
    print("  주의: 역산은 산정근거를 요구하는 도구이지 정답 금액이 아님.")
    print("        지적은 '재산정 후 제출 바람'으로 닫을 것.")
    return 0


def cmd_maint(args: argparse.Namespace) -> int:
    dev_supply = supply_price(args.dev_amount, args.vat_included)
    maint_supply = supply_price(args.maint_amount, args.vat_included)
    years = args.months / 12

    lo = dev_supply * MAINT_RATE_MIN * years
    hi = dev_supply * MAINT_RATE_MAX * years
    monthly = maint_supply / args.months if args.months else 0.0

    print(f"[유지관리·운영비 검증]  요율제 {MAINT_RATE_MIN:.0%}~{MAINT_RATE_MAX:.0%} · 투입공수 양방향")
    print(f"  개발비 공급가       {won(dev_supply)}")
    print(f"  유지관리비 공급가   {won(maint_supply)}  ({args.months}개월 = {years:.2f}년)")
    print()
    if hi > 0:
        print(f"  요율제 환산 범위    {won(lo)} ~ {won(hi)}")
        if maint_supply > hi:
            over = maint_supply / hi
            print(f"  → 상한 대비 {over:.0%} — **요율제 기준 과다**")
        elif maint_supply < lo:
            under = maint_supply / lo
            print(f"  → 하한 대비 {under:.0%} — **요율제 기준 과소**")
        else:
            print("  → 요율제 범위 내")
    else:
        # 개발비 0 = 운영유지관리 단독 사업. 요율제는 성립하지 않는다.
        print("  요율제 환산 범위    산정 불가 (개발비 0 — 개발 선행이 없는 사업)")
        print("  → 요율제로는 검증 불가. 아래 투입공수로만 판단할 것.")
    print()
    print(f"  월 단가(공급가)     {won(monthly)}")
    if args.monthly_rate:
        mm = monthly / args.monthly_rate
        print(f"  월 노임단가 {won(args.monthly_rate)} 기준 → 약 {mm:.2f} MM/월")
        if mm < 0.5:
            print("  → 상시 헬프데스크·장애대응을 감당할 수 없는 수준")
    else:
        print("  (--monthly-rate 로 월 노임단가를 주면 MM 환산까지 계산)")
    print()
    print("  판독: 요율제로 과다 + 투입공수로 과소가 동시에 성립하면")
    print("        '어느 방식으로도 설명되지 않음 = 산정방식 미적용'으로 지적할 것.")
    return 0


def cmd_sum(args: argparse.Namespace) -> int:
    items = [float(x) for x in args.items.split(",") if x.strip() != ""]
    total_items = sum(items)
    label = "VAT 포함" if args.vat_included else "VAT 제외"

    print(f"[합계·부가세·추정가격 정합]  항목 {len(items)}건 ({label})")
    for i, v in enumerate(items, 1):
        share = v / total_items * 100 if total_items else 0
        print(f"  {i:>2}. {won(v):>16}   {share:5.1f}%")
    print(f"  {'항목 합계':<6} {won(total_items):>16}")

    if args.total is not None:
        diff = total_items - args.total
        print(f"  {'명시 합계':<6} {won(args.total):>16}")
        if abs(diff) < 1:
            print("  → 일치")
        else:
            print(f"  → **불일치 {won(abs(diff))}** ({'항목 초과' if diff > 0 else '항목 부족'})")

    base = args.total if args.total is not None else total_items
    est_price = base / (1 + VAT_RATE) if args.vat_included else base
    if args.vat_included:
        print(f"  추정가격(÷1.1)      {won(est_price)}")
    else:
        print(f"  추정가격            {won(est_price)}  (이미 VAT 제외)")
        print(f"  VAT 포함 환산       {won(base * (1 + VAT_RATE))}")

    print()
    if est_price > SIMPLIFIED_REVIEW_LIMIT:
        print(f"  심의 구분: 추정가격이 {won(SIMPLIFIED_REVIEW_LIMIT)} 초과 → **정식 심의**")
        print("            (적정 사업기간 산정 주체도 과업심의위원회 — 지침 §10②③)")
    else:
        print(f"  심의 구분: 추정가격 {won(SIMPLIFIED_REVIEW_LIMIT)} 이하 → 간소화 심의 대상")
        print("            (대학 운영지침 §5③1호 — 서면심의 가능 여부 확인)")

    print()
    print("  확인: 항목별로 VAT 포함 여부가 명시되어 있는지, 단가 × 수량 형식인지,")
    print("        직접경비 세부내역이 있는지 함께 볼 것 (checklist.md 축 1).")
    return 0


def productivity_for(fp: float) -> int:
    """지침 별표 1의 규모 구간별 1인 생산성(FP/MM)."""
    for lo, hi, val in PRODUCTIVITY_BANDS:
        if lo <= fp < hi:
            return val
    return PRODUCTIVITY_BANDS[-1][2]


def capacity_for(capacity_mm: float) -> tuple[float, int]:
    """투입공수(MM)로 소화 가능한 FP 상한과 그때의 1인 생산성.

    PRODUCTIVITY_BANDS 는 단조가 아니라(19/22/24/22) `capacity_mm * prod` 이
    그 구간 안에 떨어지는 자기정합 해가 아예 없는 공수 구간이 존재한다
    (약 125~136 MM). 구간마다 도달 가능한 최댓값 `min(capacity_mm*prod, hi)`
    을 구해 그중 최대를 택하면 해가 항상 존재하고, 첫 일치 구간에서 break 해
    상한을 과소보고하던 문제(90MM → 1,980 대신 2,160)도 없어진다.
    """
    best = (0.0, PRODUCTIVITY_BANDS[0][2])
    for lo, hi, prod in PRODUCTIVITY_BANDS:
        reach = capacity_mm * prod
        if reach < lo:                        # 이 구간에는 도달조차 못 함
            continue
        candidate = min(reach, hi)
        if candidate > best[0]:
            best = (candidate, prod)
    return best


def cmd_period(args: argparse.Namespace) -> int:
    print("[적정 개발기간]  「SW사업 계약 및 관리감독에 관한 지침」 별표 1")

    if args.fp is not None:
        fp = args.fp
        prod = productivity_for(fp)
        one_person_months = fp / prod
        print(f"  ① 사업규모          {fp:,.0f} FP")
        print(f"  ② 1인 생산성        {prod} FP/MM  (규모 구간 적용)")
        print(f"  ③ 1인 총투입기간    {one_person_months:,.2f} 개월")
        print(f"  ④ 적정 개발인력 수  {args.headcount} 명")
        print(f"  ⑤ 전체 개발기간     {one_person_months / args.headcount:,.2f} 개월")
    elif args.months is not None:
        # 역산: 제시된 기간·인력으로 소화 가능한 FP 상한
        capacity_mm = args.months * args.headcount
        cap, prod = capacity_for(capacity_mm)
        print(f"  제시 개발기간       {args.months} 개월")
        print(f"  적정 개발인력 수    {args.headcount} 명")
        print(f"  총 투입공수         {capacity_mm:,.1f} MM")
        print(f"  1인 생산성          {prod} FP/MM")
        print(f"  → 소화 가능 규모    약 {cap:,.0f} FP 이하")
        print()
        print("  판독: 이 상한을 과업 요구사항 규모와 대조한다.")
        print("        요구사항이 상한을 크게 넘으면 기간 또는 인력 산정이 성립하지 않는다.")
    else:
        print("  --fp 또는 --months 중 하나를 지정할 것", file=sys.stderr)
        return 2

    print()
    print("  확인 (legal-basis.md §3·§4):")
    print("   - 별표 1 대상사업인가 — 컨설팅·운영유지관리·상용SW 도입(커스터마이징 포함)은 제외")
    print("   - 사업금액 1억원 초과면 산정 주체는 과업심의위원회 (지침 §10②③)")
    print("   - 제안요청서에 '적정 사업기간 산정 기준에 따른 사업' 명시 + 별지 제4호서식")
    print("     첨부 여부, 그 서식에서 위원명·서명이 제외되었는지 (지침 §10④)")
    print("   - 유사사업 자료는 g2b.go.kr·spir.kr 조사자료여야 함 (업체 제출 자사실적 아님)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="cost_check.py",
        description="SW사업 대가 역산 검증 (SW사업 대가산정 가이드 2025년 개정판 기준)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fp", help="개발비 → 환산 기능점수 (과소산정 탐지)")
    f.add_argument("--amount", type=float, required=True, help="계상 개발비")
    f.add_argument("--vat-included", action="store_true", help="금액이 부가세 포함이면 지정")
    f.add_argument("--profit-rate", type=float, default=DEFAULT_PROFIT_RATE, help="이윤율 (기본 0.25)")
    f.add_argument("--size-coef", type=float, default=SIZE_COEF_UNDER_500FP,
                   help="규모 보정계수 (기본 1.28 = 500FP 미만)")
    f.add_argument("--other-coef", type=float, default=1.0,
                   help="연계복잡성·성능·호환성·보안성 보정계수의 곱 (기본 1.0)")
    f.set_defaults(func=cmd_fp)

    m = sub.add_parser("maint", help="유지관리·운영비 → 요율제/투입공수 양방향 검증")
    m.add_argument("--dev-amount", type=float, required=True, help="개발비")
    m.add_argument("--maint-amount", type=float, required=True, help="유지관리·운영비 총액")
    m.add_argument("--months", type=positive_int, required=True, help="유지관리·운영 기간(개월)")
    m.add_argument("--vat-included", action="store_true", help="두 금액이 부가세 포함이면 지정")
    m.add_argument("--monthly-rate", type=float, default=None,
                   help="SW기술자 월 노임단가 (주면 MM 환산까지 계산)")
    m.set_defaults(func=cmd_maint)

    s = sub.add_parser("sum", help="항목 합계·부가세·추정가격 정합 검증")
    s.add_argument("--items", required=True, help="쉼표로 구분한 항목 금액 (예: 50000000,31000000,...)")
    s.add_argument("--total", type=float, default=None, help="문서에 명시된 합계")
    s.add_argument("--vat-included", action="store_true", help="금액이 부가세 포함이면 지정")
    s.set_defaults(func=cmd_sum)

    pd = sub.add_parser("period", help="적정 개발기간 산정/역산 (지침 별표 1)")
    g = pd.add_mutually_exclusive_group(required=True)
    g.add_argument("--fp", type=positive_float, help="사업규모(FP) → 전체 개발기간 산정")
    g.add_argument("--months", type=positive_float, help="제시된 개발기간(개월) → 소화 가능 FP 상한 역산")
    pd.add_argument("--headcount", type=positive_float, default=1.0, help="적정 개발인력 수 (기본 1명)")
    pd.set_defaults(func=cmd_period)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
