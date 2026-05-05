"use client";

import { ChartConfig } from "../lib/types";

type PlotChartProps = {
  chartConfig: ChartConfig | null;
  rows: Array<Record<string, string | number | null>>;
};

function toNumber(value: string | number | null | undefined) {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value !== "string") {
    return 0;
  }
  const parsed = Number(value.replace(/[,%]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatTick(value: number) {
  if (Math.abs(value) >= 1000) {
    return `${Math.round(value / 1000)}k`;
  }
  return String(Math.round(value));
}

function formatValueLabel(value: number) {
  if (Math.abs(value) >= 10000) {
    return `${Math.round(value / 1000)}k`;
  }
  return String(Math.round(value));
}

export function PlotChart({ chartConfig, rows }: PlotChartProps) {
  const yColumn = chartConfig?.y?.[0] ?? null;
  if (!chartConfig?.type || !chartConfig.x || !yColumn || !rows.length) {
    return null;
  }

  const points = rows.map((row) => ({
    label: String(row[chartConfig.x ?? ""] ?? ""),
    value: toNumber(row[yColumn]),
  }));
  const maxValue = Math.max(...points.map((point) => point.value), 0);

  if (!maxValue) {
    return null;
  }

  const width = 640;
  const height = chartConfig.type === "line" ? 278 : 300;
  const fittedWidth = Math.min(940, Math.max(560, points.length * 118 + 160));
  const padding = { top: 24, right: 28, bottom: points.length > 8 ? 64 : 46, left: 64 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const step = innerWidth / points.length;
  const barWidth = Math.min(52, step * 0.52);
  const chartBottom = padding.top + innerHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(maxValue * ratio));
  const linePoints = points
    .map((point, index) => {
      const x = padding.left + step * index + step / 2;
      const y = chartBottom - (point.value / maxValue) * innerHeight;
      return `${x},${y}`;
    })
    .join(" ");

  const labelStride = Math.max(1, Math.ceil(points.length / 6));
  const shouldAngleLabels = points.length > 8;
  const maxPointIndex = points.findIndex((point) => point.value === maxValue);
  const maxPoint = points[maxPointIndex];
  const maxPointX = maxPointIndex >= 0 ? padding.left + step * maxPointIndex + step / 2 : 0;
  const maxPointY = chartBottom - (maxValue / maxValue) * innerHeight;

  return (
    <svg
      aria-label={chartConfig.title ?? "证据图表"}
      className="svg-chart"
      role="img"
      style={{ maxWidth: `${fittedWidth}px` }}
      viewBox={`0 0 ${width} ${height}`}
    >
      {ticks.map((tick, index) => {
        const y = chartBottom - (tick / maxValue) * innerHeight;
        return (
          <g key={`${tick}-${index}`}>
            <line className="chart-grid-line" x1={padding.left} x2={width - padding.right} y1={y} y2={y} />
            <text className="chart-tick" textAnchor="end" x={padding.left - 12} y={y + 4}>
              {formatTick(tick)}
            </text>
          </g>
        );
      })}
      <line className="chart-axis" x1={padding.left} x2={width - padding.right} y1={chartBottom} y2={chartBottom} />
      {chartConfig.type === "line" ? (
        <>
          <polyline className="chart-line" points={linePoints} />
          {points.map((point, index) => {
            const x = padding.left + step * index + step / 2;
            const y = chartBottom - (point.value / maxValue) * innerHeight;
            return <circle className="chart-dot" cx={x} cy={y} key={point.label} r="4" />;
          })}
        </>
      ) : (
        points.map((point, index) => {
          const x = padding.left + step * index + (step - barWidth) / 2;
          const barHeight = (point.value / maxValue) * innerHeight;
          const y = chartBottom - barHeight;
          return (
            <rect
              className={index === 0 ? "chart-bar is-primary" : "chart-bar"}
              height={barHeight}
              key={point.label}
              width={barWidth}
              x={x}
              y={y}
            />
          );
        })
      )}
      {maxPoint && (
        <g className="chart-highlight">
          <line x1={maxPointX} x2={maxPointX} y1={maxPointY - 8} y2={chartBottom} />
          <text textAnchor="middle" x={maxPointX} y={Math.max(18, maxPointY - 14)}>
            最高 {formatValueLabel(maxPoint.value)}
          </text>
        </g>
      )}
      {points.map((point, index) => {
        if (index % labelStride !== 0 && index !== points.length - 1) {
          return null;
        }
        const x = padding.left + step * index + step / 2;
        return (
          <text
            className="chart-label"
            key={point.label}
            textAnchor={shouldAngleLabels ? "end" : "middle"}
            transform={shouldAngleLabels ? `rotate(-35 ${x} ${height - 24})` : undefined}
            x={x}
            y={height - 24}
          >
            {point.label}
          </text>
        );
      })}
      <text className="chart-axis-title" textAnchor="middle" x={width / 2} y={height - 2}>
        {chartConfig.x}
      </text>
    </svg>
  );
}
