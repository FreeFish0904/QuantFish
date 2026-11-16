import { useI18n } from "../i18n";
import { DataTable } from "../ui/DataTable/DataTable";
import { EmptyState } from "../ui/EmptyState/EmptyState";
import { buildExecutionParameterRows, type SubmissionExecutionParameters } from "./executionParameters";

export function ExecutionParametersTable({
  parameters
}: {
  parameters: SubmissionExecutionParameters | null | undefined;
}) {
  const { t } = useI18n();
  const rows = buildExecutionParameterRows(parameters, t);

  if (rows.length === 0) {
    return <EmptyState title={t("executionParameters.unavailable")} />;
  }

  return (
    <DataTable
      caption={t("executionParameters.title")}
      columns={[
        { key: "label", header: t("executionParameters.parameter"), render: (row) => row.label },
        { key: "value", header: t("executionParameters.value"), render: (row) => row.value, align: "right" }
      ]}
      getRowId={(row) => row.id}
      rows={rows}
    />
  );
}
