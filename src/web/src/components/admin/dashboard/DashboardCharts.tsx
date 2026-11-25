"use client";

import { useEffect, useId, useMemo, useState, type ReactNode } from "react";
import styles from "./AdminDashboard.module.scss";

export function AnimatedCounter({
  value,
  formatter,
  durationMs = 700,
}: {
  value: number;
  formatter?: (val: number) => string;
  durationMs?: number;
}) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let frameId = 0;
    const start = performance.now();
    const target = Number.isFinite(value) ? value : 0;

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(target * eased));
      if (progress < 1) {
        frameId = requestAnimationFrame(tick);
      }
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [value, durationMs]);

  return <>{formatter ? formatter(display) : new Intl.NumberFormat("vi-VN").format(display)}</>;
}

function buildSmoothPath(coords: { x: number; y: number }[]): string {
  if (coords.length === 0) return "";
  if (coords.length === 1) return `M ${coords[0].x} ${coords[0].y}`;
  let d = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const p0 = coords[i];
    const p1 = coords[i + 1];
    const cx = ((p0.x + p1.x) / 2).toFixed(1);
    d += ` C ${cx} ${p0.y.toFixed(1)}, ${cx} ${p1.y.toFixed(1)}, ${p1.x.toFixed(1)} ${p1.y.toFixed(1)}`;
  }
  return d;
}

export type SparklineCardProps = {
  title: string;
  value: number;
  valueFormatter?: (v: number) => string;
  subtitle: string;
  tone: "blue" | "emerald" | "violet" | "amber";
  metaTone?: "up" | "warn" | "info";
  icon: ReactNode;
  sparkPoints: number[];
  delayMs?: number;
};

const SPARK_COLORS: Record<SparklineCardProps["tone"], string> = {
  blue: "#3b82f6",
  emerald: "#10b981",
  violet: "#8b5cf6",
  amber: "#f59e0b",
};

export function KpiSparkCard({
  title,
  value,
  valueFormatter,
  subtitle,
  tone,
  metaTone = "up",
  icon,
  sparkPoints,
  delayMs = 0,
}: SparklineCardProps) {
  const gradId = useId().replace(/:/g, "");
  const strokeColor = SPARK_COLORS[tone];

  const { linePath, areaPath } = useMemo(() => {
    const pts = sparkPoints.length >= 2 ? sparkPoints : [sparkPoints[0] ?? 0, sparkPoints[0] ?? 0];
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const span = max - min || 1;
    const width = 110;
    const height = 36;
    const coords = pts.map((v, idx) => ({
      x: (idx / Math.max(1, pts.length - 1)) * width,
      y: height - 4 - ((v - min) / span) * (height - 10),
    }));
    const line = buildSmoothPath(coords);
    const area = `${line} L ${width} ${height} L 0 ${height} Z`;
    return { linePath: line, areaPath: area };
  }, [sparkPoints]);

  return (
    <div className={styles.kpiCard} style={{ animationDelay: `${delayMs}ms` }}>
      <div className={styles.kpiTop}>
        <div className={`${styles.kpiIconBox} ${styles[tone]}`}>{icon}</div>
        <div className={styles.kpiText}>
          <div className={styles.kpiTitle}>{title}</div>
          <div className={styles.kpiValue}>
            <AnimatedCounter value={value} formatter={valueFormatter} />
          </div>
        </div>
      </div>

      <div className={styles.kpiBottom}>
        <span className={`${styles.kpiMeta} ${styles[metaTone]}`}>{subtitle}</span>
        <div className={styles.sparklineWrap} aria-hidden="true">
          <svg viewBox="0 0 110 36" preserveAspectRatio="none">
            <defs>
              <linearGradient id={`spark-${gradId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={strokeColor} stopOpacity="0.32" />
                <stop offset="100%" stopColor={strokeColor} stopOpacity="0.01" />
              </linearGradient>
            </defs>
            <path d={areaPath} fill={`url(#spark-${gradId})`} />
            <path
              d={linePath}
              fill="none"
              stroke={strokeColor}
              strokeWidth="2.2"
              strokeLinecap="round"
              className={styles.sparkPath}
            />
          </svg>
        </div>
      </div>
    </div>
  );
}

export type ComboPoint = {
  label: string;
  barValue: number;
  lineValue: number;
  tooltipTitle: string;
  barLabel: string;
  lineLabel: string;
};

export function ComboBarLineChart({
  points,
  barLegend,
  lineLegend,
  formatBarAxis,
  formatBarValue,
  formatLineValue,
}: {
  points: ComboPoint[];
  barLegend: string;
  lineLegend: string;
  formatBarAxis: (val: number) => string;
  formatBarValue: (val: number) => string;
  formatLineValue: (val: number) => string;
}) {
  const gradId = useId().replace(/:/g, "");
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const chart = useMemo(() => {
    const W = 380;
    const H = 225;
    const padLeft = 34;
    const padRight = 10;
    const padTop = 16;
    const padBottom = 26;
    const plotW = W - padLeft - padRight;
    const plotH = H - padTop - padBottom;

    const maxVal = Math.max(1, ...points.map((p) => Math.max(p.barValue, p.lineValue)));

    const step = plotW / Math.max(1, points.length);
    const barW = Math.min(30, Math.max(14, step * 0.44));

    const items = points.map((pt, i) => {
      const cx = padLeft + step * i + step / 2;
      const barH = Math.max(4, (pt.barValue / maxVal) * plotH);
      const barY = padTop + plotH - barH;
      const lineY = padTop + plotH - (pt.lineValue / maxVal) * plotH;
      return {
        ...pt,
        cx,
        barX: cx - barW / 2,
        barY,
        barW,
        barH,
        lineY,
      };
    });

    const linePath = buildSmoothPath(items.map((it) => ({ x: it.cx, y: it.lineY })));
    const gridTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
      y: padTop + plotH - ratio * plotH,
      label: formatBarAxis(Math.round(maxVal * ratio)),
    }));

    return { W, H, padLeft, padRight, padTop, plotH, items, linePath, gridTicks };
  }, [points, formatBarAxis]);

  const activePoint = hoveredIdx !== null ? chart.items[hoveredIdx] : null;

  if (points.length === 0) {
    return (
      <div className={styles.comboChartContainer} style={{ justifyContent: "center", alignItems: "center", color: "var(--admin-text-muted)" }}>
        Chưa có dữ liệu biểu đồ trong phạm vi đang chọn.
      </div>
    );
  }

  return (
    <div className={styles.comboChartContainer}>
      <div className={styles.chartLegendRow}>
        <span className={styles.legendItem}>
          <span className={styles.dotBlue} />
          {barLegend}
        </span>
        <span className={styles.legendItem}>
          <span className={styles.dotViolet} />
          {lineLegend}
        </span>
      </div>

      <div className={styles.svgChartBox}>
        {activePoint && (
          <div className={styles.chartTooltip}>
            <div className={styles.ttTitle}>{activePoint.tooltipTitle}</div>
            <div className={styles.ttRow}>
              <span>{activePoint.barLabel}:</span>
              <strong>{formatBarValue(activePoint.barValue)}</strong>
            </div>
            <div className={styles.ttRow}>
              <span>{activePoint.lineLabel}:</span>
              <strong>{formatLineValue(activePoint.lineValue)}</strong>
            </div>
          </div>
        )}

        <svg viewBox={`0 0 ${chart.W} ${chart.H}`} preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id={`barGrad-${gradId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.65" />
            </linearGradient>
            <linearGradient id={`barGradHover-${gradId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.9" />
            </linearGradient>
          </defs>

          {/* Gridlines & Y labels */}
          {chart.gridTicks.map((t, idx) => (
            <g key={idx}>
              <line
                x1={chart.padLeft}
                y1={t.y}
                x2={chart.W - chart.padRight}
                y2={t.y}
                stroke="var(--admin-border-subtle, #e2e8f0)"
                strokeDasharray="3 3"
                strokeWidth="1"
              />
              <text
                x={chart.padLeft - 8}
                y={t.y + 4}
                textAnchor="end"
                fontSize="10.5"
                fill="var(--admin-text-muted, #94a3b8)"
              >
                {t.label}
              </text>
            </g>
          ))}

          {/* Bars */}
          {chart.items.map((item, idx) => (
            <g
              key={item.label + idx}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <rect
                x={item.barX}
                y={item.barY}
                width={item.barW}
                height={item.barH}
                rx={6}
                ry={6}
                fill={hoveredIdx === idx ? `url(#barGradHover-${gradId})` : `url(#barGrad-${gradId})`}
                className={styles.barRect}
                style={{ animationDelay: `${idx * 65}ms` }}
              />
              <text
                x={item.cx}
                y={chart.H - 6}
                textAnchor="middle"
                fontSize="11"
                fontWeight={hoveredIdx === idx ? "700" : "500"}
                fill={hoveredIdx === idx ? "#3b82f6" : "var(--admin-text-secondary, #64748b)"}
              >
                {item.label}
              </text>
            </g>
          ))}

          {/* Smooth Line Overlay */}
          {chart.items.length >= 2 && (
            <path
              d={chart.linePath}
              fill="none"
              stroke="#8b5cf6"
              strokeWidth="2.6"
              strokeLinecap="round"
              className={styles.comboLinePath}
            />
          )}

          {/* Dots on Line */}
          {chart.items.map((item, idx) => (
            <g
              key={`dot-${idx}`}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <circle
                cx={item.cx}
                cy={item.lineY}
                r={hoveredIdx === idx ? 6 : 4.2}
                fill="#ffffff"
                stroke="#8b5cf6"
                strokeWidth="2.5"
                className={styles.comboLineDot}
                style={{ animationDelay: `${250 + idx * 65}ms` }}
              />
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

export type DonutSegment = {
  key: string;
  label: string;
  value: number;
  color: string;
  formattedValue?: string;
};

export function DonutChartCard({
  segments,
  centerValue,
  centerLabel,
}: {
  segments: DonutSegment[];
  centerValue: string;
  centerLabel: string;
}) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const total = segments.reduce((acc, s) => acc + Math.max(0, s.value), 0);

  const radius = 56;
  const circumference = 2 * Math.PI * radius;

  const computed = useMemo(() => {
    let offsetAcc = 0;
    return segments.map((seg) => {
      const ratio = total > 0 ? Math.max(0, seg.value) / total : 0;
      const dashLen = ratio * circumference;
      const dashOffset = -offsetAcc;
      offsetAcc += dashLen;
      return {
        ...seg,
        percent: total > 0 ? Math.round(ratio * 1000) / 10 : 0,
        dashArray: `${dashLen} ${circumference}`,
        dashOffset,
      };
    });
  }, [segments, total, circumference]);

  const focused = activeKey ? computed.find((c) => c.key === activeKey) : null;

  return (
    <div className={styles.donutLayout}>
      <div className={styles.donutRingWrap}>
        <svg viewBox="0 0 148 148">
          <circle
            cx="74"
            cy="74"
            r={radius}
            fill="none"
            stroke="var(--admin-border-subtle, #f1f5f9)"
            strokeWidth="18"
          />
          {total > 0 &&
            computed.map((seg) => (
              <circle
                key={seg.key}
                cx="74"
                cy="74"
                r={radius}
                fill="none"
                stroke={seg.color}
                strokeWidth={activeKey === seg.key ? 22 : 18}
                strokeDasharray={seg.dashArray}
                strokeDashoffset={seg.dashOffset}
                strokeLinecap="butt"
                opacity={activeKey && activeKey !== seg.key ? 0.45 : 1}
                className={styles.donutSegment}
                onMouseEnter={() => setActiveKey(seg.key)}
                onMouseLeave={() => setActiveKey(null)}
              />
            ))}
        </svg>
        <div className={styles.donutCenter}>
          <span className={styles.centerNum}>
            {focused ? `${focused.percent}%` : centerValue}
          </span>
          <span className={styles.centerLbl}>
            {focused ? focused.label : centerLabel}
          </span>
        </div>
      </div>

      <div className={styles.donutLegend}>
        {computed.map((seg) => (
          <div
            key={seg.key}
            className={`${styles.donutLegendItem} ${activeKey === seg.key ? styles.active : ""}`}
            onMouseEnter={() => setActiveKey(seg.key)}
            onMouseLeave={() => setActiveKey(null)}
          >
            <div className={styles.dlLeft}>
              <span className={styles.dlDot} style={{ backgroundColor: seg.color }} />
              <span className={styles.dlName} title={seg.label}>
                {seg.label}
              </span>
            </div>
            <span className={styles.dlVal}>{seg.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
