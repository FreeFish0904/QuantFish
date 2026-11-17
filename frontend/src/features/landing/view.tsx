import { ArrowRight, ExternalLink, Layers, Moon, ShieldCheck, Sun, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { useTheme } from "../../shared/theme/ThemeContext";
import styles from "./view.module.css";

export const REPOSITORY_URL = "https://github.com/FreeFish0904/QuantFish";

const featureCards = [
  { key: "engine", icon: Zap, tone: styles.toneCyan },
  { key: "scoring", icon: ShieldCheck, tone: styles.toneEmerald },
  { key: "ops", icon: Layers, tone: styles.toneViolet }
] as const;

const pipelineSteps = ["step1", "step2", "step3", "step4"] as const;

export function LandingView() {
  const { language, setLanguage, t } = useI18n();
  const { cycleTheme, resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <span aria-hidden="true" className={styles.brandMark}>
            {t("brand.shortMark")}
          </span>
          <span className={styles.brandName}>{t("brand.name")}</span>
        </div>
        <div className={styles.topbarActions}>
          <button
            className={styles.ghostButton}
            type="button"
            aria-label={t("common.toggleTheme")}
            onClick={cycleTheme}
          >
            {isDark ? <Moon aria-hidden="true" size={17} /> : <Sun aria-hidden="true" size={17} />}
          </button>
          <button
            className={styles.ghostButton}
            type="button"
            aria-label={t("common.toggleLanguage")}
            onClick={() => setLanguage(language === "en" ? "zh" : "en")}
          >
            {language === "zh" ? "中" : "EN"}
          </button>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.hero}>
          <p className={styles.badge}>{t("landing.badge")}</p>
          <h1 className={styles.title}>{t("landing.title")}</h1>
          <p className={styles.subtitle}>{t("landing.subtitle")}</p>
          <div className={styles.actions}>
            <Link className={styles.primaryAction} to="/dashboard">
              {t("landing.primaryCta")}
              <ArrowRight aria-hidden="true" size={18} />
            </Link>
            <a
              className={styles.secondaryAction}
              href={REPOSITORY_URL}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" size={18} />
              {t("landing.secondaryCta")}
            </a>
          </div>
          <p className={styles.hint}>{t("landing.demoHint")}</p>
        </section>

        <section aria-label={t("landing.featuresTitle")} className={styles.features}>
          <h2 className={styles.sectionTitle}>{t("landing.featuresTitle")}</h2>
          <div className={styles.featureGrid}>
            {featureCards.map(({ key, icon: Icon, tone }) => (
              <article className={[styles.featureCard, tone].join(" ")} key={key}>
                <span aria-hidden="true" className={styles.featureIcon}>
                  <Icon size={19} />
                </span>
                <h3 className={styles.featureTitle}>{t(`landing.features.${key}Title`)}</h3>
                <p className={styles.featureBody}>{t(`landing.features.${key}Body`)}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-label={t("landing.pipeline.title")} className={styles.pipeline}>
          <h2 className={styles.sectionTitle}>{t("landing.pipeline.title")}</h2>
          <ol className={styles.steps}>
            {pipelineSteps.map((step, index) => (
              <li className={styles.step} key={step}>
                <span className={styles.stepIndex}>{index + 1}</span>
                <span>{t(`landing.pipeline.${step}`)}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
