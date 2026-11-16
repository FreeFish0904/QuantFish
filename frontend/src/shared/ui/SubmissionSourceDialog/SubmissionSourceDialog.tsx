import { Button } from "../Button/Button";
import { PythonCodeBlock } from "../PythonCodeBlock";
import styles from "./SubmissionSourceDialog.module.css";

type SubmissionSourceDialogProps = {
  closeLabel: string;
  error?: string;
  isLoading: boolean;
  loadingLabel: string;
  onClose: () => void;
  pythonLabel: string;
  source?: string;
  title: string;
  unavailableLabel: string;
};

export function SubmissionSourceDialog({
  closeLabel,
  error,
  isLoading,
  loadingLabel,
  onClose,
  pythonLabel,
  source,
  title,
  unavailableLabel
}: SubmissionSourceDialogProps) {
  return (
    <div className={styles.dialogBackdrop}>
      <div aria-labelledby="submission-source-title" aria-modal="true" className={styles.dialog} role="dialog">
        <div className={styles.modalHeader}>
          <h2 id="submission-source-title">{title}</h2>
          <Button onClick={onClose} type="button" variant="ghost">
            {closeLabel}
          </Button>
        </div>
        {source !== undefined ? <PythonCodeBlock label={pythonLabel} source={source} /> : null}
        {source === undefined && error ? <p className={styles.muted}>{error}</p> : null}
        {source === undefined && !error ? (
          <p className={styles.muted}>{isLoading ? loadingLabel : unavailableLabel}</p>
        ) : null}
      </div>
    </div>
  );
}
