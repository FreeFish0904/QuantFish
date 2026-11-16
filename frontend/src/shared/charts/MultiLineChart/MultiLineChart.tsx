import {
  LightweightSvgChart,
  lightweightDomainForSeries,
  lightweightTicks
} from "../LightweightSvgChart/LightweightSvgChart";
import { useI18n } from "../../i18n";
import { EmptyState } from "../../ui/EmptyState/EmptyState";
import styles from "./MultiLineChart.module.css";

function chartTitleId(title: string): string {
  return `sf-chart-title-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}`;
}

export type MultiLineChartSeries = {
  id: string;
  name: string;
  color: string;
};

export type MultiLineChartProps<T extends Record<string, unknown>> = {
  data: T[];
  series: MultiLineChartSeries[];
  xKey: keyof T;
  title: string;
  height?: number;
};

export function MultiLineChart<T extends Record<string, unknown>>({
  data,
  series,
  xKey,
  title,
  height = 280
}: MultiLineChartProps<T>) {
  const { t } = useI18n();
  if (data.length === 0 || series.length === 0) {
    return <EmptyState title={t("charts.noDataTitle")} description={t("charts.multiLineChartNoDataDescription")} />;
  }

  const yKeys = series.map((item) => item.id);
  const yDomain = lightweightDomainForSeries(data, yKeys, true);
  const yTicks = lightweightTicks(yDomain);
  const titleId = chartTitleId(title);

  return (
    <div aria-label={title} aria-labelledby={titleId} className={styles.chart} role="img">
      <span className={styles.chartTitle} id={titleId}>{title}</span>
      <div className={styles.legend} aria-hidden="true">
        {series.map((item) => (
          <span className={styles.legendItem} key={item.id}>
            <span className={styles.swatch} style={{ background: item.color }} />
            {item.name}
          </span>
        ))}
      </div>
      <div className={styles.frame}>
        <LightweightSvgChart
          data={data}
          height={height}
          series={series.map((item) => ({
            color: item.color,
            dataKey: item.id,
            name: item.name,
            strokeWidth: 2,
            type: "line"
          }))}
          xKey={xKey}
          yDomain={yDomain}
          yTicks={yTicks}
        />
      </div>
    </div>
  );
}
