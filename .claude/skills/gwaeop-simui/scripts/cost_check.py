#!/usr/bin/env python3
"""SW사업 대가·기간 검증 — 결정론적 계산기.

fp/maint/commercial/sum : 「SW사업 대가산정 가이드」(2025년 개정판) 기준 대가 역산
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
# 표4-4 용역 SW 유지관리 난이도(TMP) 산정 평가표 — (단순, 보통, 복잡) 점수, 총점 0~100
TMP_FACTORS = [
    ("유지관리 횟수", (0, 14, 27)),      # 연 4회 이하 / 12회 이하 / 12회 초과
    ("시스템 사용자수", (0, 8, 18)),     # 내부 25%·대국민 1만 이하 / 50%·10만 이하 / 초과
    ("시스템 중요도", (0, 17, 31)),      # 표4-3 4·5급 / 3급 / 1·2급
    ("타시스템 연계", (0, 6, 11)),       # 없음 / 1~2개 / 3개 이상
    ("오류복구 신속성", (0, 6, 13)),     # 12시간 초과 / 12시간 이내 / 6시간 이내
]
TMP_LEVELS = {"단순": 0, "보통": 1, "복잡": 2}
# 표4-10 상용SW 유지관리 측정 등급별 적용요율 (최초 Licence 구매 계약금액 기준)
COMMERCIAL_MAINT_RATES = {1: 0.20, 2: 0.18, 3: 0.16, 4: 0.14, 5: 0.12}
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


def tmp_from_levels(levels: str) -> int:
    """표4-4 순서(횟수,사용자수,중요도,연계,신속성)의 단순/보통/복잡 5개 → TMP 총점."""
    parts = [x.strip() for x in levels.split(",")]
    if len(parts) != len(TMP_FACTORS) or any(x not in TMP_LEVELS for x in parts):
        raise ValueError(
            f"단순/보통/복잡 {len(TMP_FACTORS)}개를 "
            f"{','.join(n for n, _ in TMP_FACTORS)} 순서로 줄 것: {levels}")
    return sum(scores[TMP_LEVELS[x]] for x, (_, scores) in zip(parts, TMP_FACTORS))


def maint_rate_for(tmp: float) -> float:
    """유지관리 요율 = 10 + 5 × (TMP ÷ 100) [%]."""
    return (10 + 5 * tmp / 100) / 100


def tmp_arg(value: str) -> int:
    v = int(value)
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError(f"TMP는 0~100: {value}")
    return v


def levels_arg(value: str) -> str:
    try:
        tmp_from_levels(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    return value


def cmd_maint(args: argparse.Namespace) -> int:
    dev_supply = supply_price(args.dev_amount, args.vat_included)
    maint_supply = supply_price(args.maint_amount, args.vat_included)
    direct = supply_price(args.direct_expense, args.vat_included)
    years = args.months / 12

    # 요율제 유지관리비 = 개발비 × 요율 + 직접경비 — 비교는 직접경비를 뺀 금액으로 한다.
    rate_part = maint_supply - direct
    lo = dev_supply * MAINT_RATE_MIN * years
    hi = dev_supply * MAINT_RATE_MAX * years
    monthly = maint_supply / args.months if args.months else 0.0

    print(f"[유지관리·운영비 검증]  요율제 {MAINT_RATE_MIN:.0%}~{MAINT_RATE_MAX:.0%} · 투입공수 양방향")
    print(f"  개발비 공급가       {won(dev_supply)}")
    print(f"  유지관리비 공급가   {won(maint_supply)}  ({args.months}개월 = {years:.2f}년)")
    if direct:
        print(f"  직접경비            {won(direct)}  → 요율 적용분 {won(rate_part)}")
    print()
    tmp = tmp_from_levels(args.tmp_levels) if args.tmp_levels else args.tmp
    if hi > 0 and tmp is not None:
        rate = maint_rate_for(tmp)
        expected = dev_supply * rate * years + direct
        print(f"  TMP {tmp}점 → 요율 {rate * 100:.2f}%  (표4-4·10 + 5 × TMP/100)")
        print(f"  TMP 기준 산정액     {won(expected)}")
        if abs(maint_supply - expected) < 1:
            print("  → TMP 산정액과 일치")
        else:
            print(f"  → TMP 산정액 대비 {maint_supply / expected:.0%}"
                  f" — {'과다' if maint_supply > expected else '과소'} (난이도 판정 근거 요구)")
        print()
    if hi > 0:
        print(f"  요율제 환산 범위    {won(lo)} ~ {won(hi)}")
        if rate_part > hi:
            over = rate_part / hi
            print(f"  → 상한 대비 {over:.0%} — **요율제 기준 과다**")
        elif rate_part < lo:
            under = rate_part / lo
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


def cmd_commercial(args: argparse.Namespace) -> int:
    license_supply = supply_price(args.license_amount, args.vat_included)
    rate = COMMERCIAL_MAINT_RATES[args.grade]
    years = args.months / 12
    expected = license_supply * rate * years

    print(f"[상용SW 유지관리비 검증]  가이드 {GUIDE_VERSION} 표4-10 · 등급별 요율")
    print(f"  최초 Licence 구매 계약금액(공급가)  {won(license_supply)}")
    print(f"  유지관리 등급       {args.grade}등급 → 요율 {rate:.0%}  ({args.months}개월 = {years:.2f}년)")
    print(f"  등급 기준 산정액    {won(expected)}  (부가세 별도)")
    if args.maint_amount is not None:
        maint_supply = supply_price(args.maint_amount, args.vat_included)
        print(f"  계상 유지관리비     {won(maint_supply)}")
        if abs(maint_supply - expected) < 1:
            print("  → 등급 산정액과 일치")
        else:
            actual_rate = maint_supply / license_supply / years if license_supply else 0.0
            verdict = "과다" if maint_supply > expected else "과소"
            print(f"  → 실효 요율 {actual_rate:.1%} — 등급 기준 **{verdict}** (등급 판정 근거·협의 조정 사유 요구)")
    print()
    print("  확인: 표4-9 등급별 서비스 수준(긴급/장애 처리시간·방문 여부·교육)이 과업지시서에 명시됐는지,")
    print("        조달청 쇼핑몰 등록상품이면 조달청 단가 우선, 메이저 업그레이드·커스터마이징은 미포함,")
    print("        정보보호제품이면 보안성 지속 서비스비와 중복 산정 금지 (가이드 2.2.5).")
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

    # 총 사업금액은 부가세 제외(= 추정가격)로 판정한다 — 조문에 포함 여부 명시가 없어
    # 담당자 확인으로 정한 운영 기준(legal-basis.md §5 "금액 기준 — 부가세").
    vat_inclusive = est_price * (1 + VAT_RATE)
    print()
    if est_price > SIMPLIFIED_REVIEW_LIMIT:
        print(f"  심의 구분: 총 사업금액(부가세 제외) {won(est_price)} > {won(SIMPLIFIED_REVIEW_LIMIT)} → **정식 심의**")
        print("            (적정 사업기간 산정 주체도 과업심의위원회 — 지침 §10②③)")
    else:
        print(f"  심의 구분: 총 사업금액(부가세 제외) {won(est_price)} ≤ {won(SIMPLIFIED_REVIEW_LIMIT)} → 간소화 심의 대상")
        print("            (대학 운영지침 §5③1호 — 서면심의 가능 여부 확인)")
        if vat_inclusive > SIMPLIFIED_REVIEW_LIMIT:
            print(f"  ** 경계 구간: 부가세 포함 {won(vat_inclusive)}은 1억원 초과 — 포함 기준으로 읽으면 정식 심의로 갈림."
                  " 발주 문서가 어느 금액을 기준으로 삼는지 확인할 것")

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
    # 요건 문구는 checklist.md 축 2가 정본 — 여기서는 행 번호만 가리킨다(중복 서술 금지).
    print("  확인: checklist.md 축 2 — 대상사업 2-0 · 산정 주체 2-5 · 유사사업 2-4 · 첨부 요건 2-6·2-7·2-11")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="cost_check.py",
        description="SW사업 대가 역산 검증 (SW사업 대가산정 가이드 2025년 개정판 기준)",
        epilog="""사용 예:
  # 개발비 → 환산 기능점수 (과소산정 탐지)
  cost_check.py fp --amount 50000000 --vat-included

  # 운영·유지관리비 → 요율제(10~15%) 대비 위치
  cost_check.py maint --dev-amount 50000000 --maint-amount 31000000 \\
      --months 36 --vat-included

  # 난이도(TMP)를 알면 정확한 요율까지 (표4-4, 가이드 적용사례)
  cost_check.py maint --dev-amount 249222058 --maint-amount 31865302 --months 12 \\
      --tmp-levels 보통,보통,보통,단순,보통 --direct-expense 1335600

  # 상용SW 유지관리비 → 등급별 요율(1등급 20% ~ 5등급 12%)
  cost_check.py commercial --license-amount 50000000 --grade 3 --maint-amount 8000000

  # 항목 합계·VAT·추정가격 정합
  cost_check.py sum --total 150000000 \\
      --items 50000000,31000000,54000000,6000000,9000000,0 --vat-included

  # 적정 개발기간 (지침 별표 1) — 제시 기간으로 소화 가능한 규모 상한
  cost_check.py period --months 3 --headcount 3

  # 규모를 아는 경우 정방향 산정
  cost_check.py period --fp 470 --headcount 3
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    m.add_argument("--direct-expense", type=float, default=0.0,
                   help="유지관리비에 포함된 직접경비 (요율 비교에서 제외)")
    t = m.add_mutually_exclusive_group()
    t.add_argument("--tmp", type=tmp_arg, default=None, help="유지관리 난이도 총점 TMP (0~100)")
    t.add_argument("--tmp-levels", type=levels_arg, default=None,
                   help="표4-4 난이도 5개 — 횟수,사용자수,중요도,연계,신속성 순 단순/보통/복잡"
                        " (예: 보통,보통,보통,단순,보통)")
    m.set_defaults(func=cmd_maint)

    c = sub.add_parser("commercial", help="상용SW 유지관리비 → 등급별 요율(표4-10) 검증")
    c.add_argument("--license-amount", type=positive_float, required=True,
                   help="최초 Licence 구매 계약금액")
    c.add_argument("--grade", type=int, choices=sorted(COMMERCIAL_MAINT_RATES), required=True,
                   help="유지관리 등급 1~5 (표4-9 서비스 수준으로 판정)")
    c.add_argument("--maint-amount", type=float, default=None, help="계상된 상용SW 유지관리비")
    c.add_argument("--months", type=positive_int, default=12, help="유지관리 기간(개월, 기본 12)")
    c.add_argument("--vat-included", action="store_true", help="금액이 부가세 포함이면 지정")
    c.set_defaults(func=cmd_commercial)

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
