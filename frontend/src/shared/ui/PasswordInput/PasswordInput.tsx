import { Eye, EyeOff } from "lucide-react";
import { useState, type InputHTMLAttributes } from "react";

import { useI18n } from "../../i18n";
import styles from "./PasswordInput.module.css";

export type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  inputClassName?: string;
};

export function PasswordInput({
  className = "",
  disabled,
  inputClassName = "",
  ...inputProps
}: PasswordInputProps) {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  const toggleLabel = visible ? t("common.hidePassword") : t("common.showPassword");

  return (
    <span className={[styles.wrapper, className].join(" ")}>
      <input
        {...inputProps}
        className={[styles.input, inputClassName].join(" ")}
        disabled={disabled}
        type={visible ? "text" : "password"}
      />
      <button
        aria-label={toggleLabel}
        aria-pressed={visible}
        className={styles.toggle}
        disabled={disabled}
        onClick={() => setVisible((current) => !current)}
        title={toggleLabel}
        type="button"
      >
        {visible ? <EyeOff aria-hidden="true" size={17} /> : <Eye aria-hidden="true" size={17} />}
      </button>
    </span>
  );
}
