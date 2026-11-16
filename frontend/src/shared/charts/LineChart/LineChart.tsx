import {
  LightweightSvgChart,
  lightweightDomainForSeries,
  lightweightTicks
} from "../LightweightSvgChart/LightweightSvgChart";
import { useI18n } from "../../i18n";
import { EmptyState } from "../../ui/EmptyState/EmptyState";
import styles from "./LineChart.module.css";

function chartTitleId(title: string): string {
  return `sf-chart-title-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}`;
}

export type LineChartProps<T extends Record<string, unknown>> = {
  data: T[];
  xKey: keyof T;
  yKey: keyof T;
  color: string;
  title: string;
  height?: number;
};

export function LineChart<T extends Record<string, unknown>>({
  data,
  xKey,
  yKey,
  color,
  title,
  height = 280
}: LineChartProps<T>) {
  const { t } = useI18n();
  if (data.length === 0) {
    return <EmptyState title={t("charts.noDataTitle")} description={t("charts.lineChartNoDataDescription")} />;
  }

  const yKeyName = String(yKey);
  const yDomain = lightweightDomainForSeries(data, [yKeyName], true);
  const yTicks = lightweightTicks(yDomain);
  const titleId = chartTitleId(title);

  return (
    <div aria-label={title} aria-labelledby={titleId} className={styles.chart} role="img">
      <span className={styles.chartTitle} id={titleId}>{title}</span>
      <div className={styles.legend} aria-hidden="true">
        <span className={styles.legendItem}>
          <span className={styles.swatch} style={{ background: color }} />
          {title}
        </span>
      </div>
      <div className={styles.frame}>
        <LightweightSvgChart
          data={data}
          height={height}
          series={[{ color, dataKey: yKeyName, name: title, strokeWidth: 2, type: "line" }]}
          xKey={xKey}
          yDomain={yDomain}
          yTicks={yTicks}
        />
      </div>
    </div>
  );
}
