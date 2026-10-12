import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { EditableSettings, SettingsChanges, SettingsPublished } from "@/api/types";
import { ReviewDialog } from "@/components/admin/ReviewDialog";
import {
  CheckboxSetting,
  ChoiceSetting,
  NumberSetting,
  SwitchSetting,
} from "@/components/admin/SettingControls";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t, tOr } from "@/config/terminology";
import {
  formatWhen,
  useAdminSettings,
  useConfigVersions,
  usePreviewSettings,
  usePublishSettings,
} from "@/domain/admin";
import { formatInr } from "@/domain/cases";
import { SEVERITIES } from "@/domain/crossVerification";
import { useCan } from "@/domain/session";
import {
  changesOf,
  currentValue,
  draftCounts,
  fieldKey,
  fieldsOf,
  fieldState,
  formatAmount,
  isPublished,
  unitLabel,
  yesNoText,
  type Draft,
  type Editor,
} from "@/domain/settings";

// Settings (F-00.6): the tolerances, policy norm thresholds, cross-check rules and approval matrix
// an Administrator changes on screen. Edits stay in a draft until they are reviewed with the
// engine and published, with a note, as a new configuration version. Without config.publish the
// same values are shown read-only.

export const Route = createFileRoute("/admin/settings")({ component: Settings });

const FAMILIES = ["eligibility", "ratios", "security_cover", "documentation"] as const;

const HEAD =
  "border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground";
const GROUP = "bg-surface-muted px-4 py-1.5 text-left text-[11.5px] font-semibold text-foreground";
const SUBHEAD = "px-4 pb-1 pt-3 text-[12.5px] font-semibold text-foreground";
const HELP = "px-4 pb-2 text-[12px] text-muted-foreground";

function Settings() {
  const settings = useAdminSettings();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={settings}>{(s) => <SettingsForm settings={s} />}</QueryView>
    </div>
  );
}

function SettingsForm({ settings: s }: { settings: EditableSettings }) {
  const canPublish = useCan("config.publish");
  const preview = usePreviewSettings();
  const publish = usePublishSettings();
  const [draft, setDraft] = useState<Draft>({});
  const [reviewing, setReviewing] = useState<SettingsChanges | null>(null);
  const [published, setPublished] = useState<SettingsPublished | null>(null);
  const fields = useMemo(() => fieldsOf(s), [s]);
  const counts = draftCounts(fields, draft);

  const edit: Editor = {
    readOnly: !canPublish,
    state: (key) => {
      const spec = fields.get(key);
      return spec ? fieldState(spec, draft, key) : { value: "", changed: false, invalid: false };
    },
    current: (key) => {
      const spec = fields.get(key);
      return spec ? currentValue(spec, draft, key) : undefined;
    },
    set: (key, value) =>
      setDraft((d) => {
        const spec = fields.get(key);
        const { [key]: _, ...rest } = d;
        return spec && isPublished(spec, value) ? rest : { ...rest, [key]: value };
      }),
    undo: (key) =>
      setDraft((d) => {
        const { [key]: _, ...rest } = d;
        return rest;
      }),
  };

  const review = () => {
    const changes = changesOf(s, draft);
    publish.reset();
    preview.mutate(changes);
    setReviewing(changes);
  };

  const submit = (changes: SettingsChanges, note: string) =>
    publish.mutate(
      { note, changes },
      {
        onSuccess: (result) => {
          setPublished(result);
          setDraft({});
          setReviewing(null);
        },
      },
    );

  return (
    <>
      <Header settings={s} canPublish={canPublish} />
      {published && <Published result={published} />}
      <TolerancesPanel settings={s} edit={edit} />
      <PolicyPanel settings={s} edit={edit} />
      <RulesPanel settings={s} edit={edit} />
      <MatrixPanel settings={s} edit={edit} />
      {canPublish && counts.changed > 0 && (
        <div
          className="sticky bottom-0 z-10 -mx-4 -mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border bg-surface px-4 py-2.5 shadow-[0_-2px_6px_rgba(0,0,0,0.05)] sm:-mx-6 sm:px-6"
          data-testid="settings-bar"
        >
          <span className="text-[13px] font-medium" data-testid="settings-count">
            {counts.changed === 1
              ? t("admin.settings.bar.one")
              : t("admin.settings.bar.many", { n: counts.changed })}
          </span>
          {counts.invalid > 0 && (
            <span className="text-[12px] text-destructive">{t("admin.settings.bar.fixFirst")}</span>
          )}
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={() => setDraft({})}
              className="h-8 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
              data-testid="settings-discard"
            >
              {t("admin.settings.bar.discard")}
            </button>
            <button
              type="button"
              disabled={counts.invalid > 0}
              onClick={review}
              className="h-8 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
              data-testid="settings-review"
            >
              {t("admin.settings.bar.review")}
            </button>
          </div>
        </div>
      )}
      {reviewing && (
        <ReviewDialog
          preview={preview}
          publish={publish}
          changes={reviewing}
          onPublish={(note) => submit(reviewing, note)}
          onClose={() => setReviewing(null)}
        />
      )}
    </>
  );
}

/** The version in force: its number, when and by whom it was published, and whether on screen. */
function Header({ settings: s, canPublish }: { settings: EditableSettings; canPublish: boolean }) {
  const versions = useConfigVersions();
  const list = versions.data ?? [];
  const index = list.findIndex((v) => v.version === s.version);
  return (
    <div className="space-y-1" data-testid="settings-header">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
        <span className="font-medium">
          {index >= 0
            ? t("admin.settings.versionInForce", { n: list.length - index })
            : t("admin.settings.inForce")}
        </span>
        <span className="text-[12.5px] text-muted-foreground">
          {t("admin.settings.publishedBy", { when: formatWhen(s.published_at), author: s.author })}
        </span>
        {s.origin === "app" && <Chip tone="info">{t("admin.config.edited")}</Chip>}
      </p>
      <p className="text-[12px] text-muted-foreground" data-testid="settings-mode">
        {canPublish ? t("admin.settings.editHelp") : t("admin.settings.readOnly")}
      </p>
    </div>
  );
}

function Published({ result }: { result: SettingsPublished }) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded border border-positive/30 bg-positive-soft px-4 py-2.5 text-[12.5px]"
      data-testid="settings-published"
    >
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
      <div className="min-w-0">
        <p className="font-medium text-positive">
          {result.cases_rerun === 1
            ? t("admin.settings.publishedOne")
            : t("admin.settings.published", { n: result.cases_rerun })}
        </p>
        {result.cases_failed.length > 0 && (
          <p className="text-destructive" data-testid="settings-failed">
            {t("admin.settings.failed", { cases: result.cases_failed.join(", ") })}
          </p>
        )}
      </div>
    </div>
  );
}

/** Rule ids as chips, each titled with its rule. */
function RuleIds({ ids, settings }: { ids: string[]; settings: EditableSettings }) {
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <Chip
          key={id}
          tone="muted"
          title={settings.rules.find((r) => r.id === id)?.title ?? id}
          className="font-mono"
        >
          {id}
        </Chip>
      ))}
    </span>
  );
}

function TolerancesPanel({ settings: s, edit }: { settings: EditableSettings; edit: Editor }) {
  return (
    <Panel
      title={t("admin.settings.tolerances.title")}
      subtitle={t("admin.settings.tolerances.subtitle")}
      testId="settings-tolerances"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-[12.5px]">
          <thead>
            <tr className={HEAD}>
              <th className="px-4 py-2 font-medium">{t("admin.settings.tolerances.setting")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.tolerances.value")}</th>
              <th className="px-4 py-2 font-medium">{t("admin.settings.tolerances.usedBy")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {s.tolerances.map((x) => (
              <tr key={x.key} className="align-top" data-testid={`tolerance-${x.key}`}>
                <td className="px-4 py-2">{x.label}</td>
                <td className="px-3 py-2">
                  <NumberSetting
                    edit={edit}
                    field={fieldKey.tolerance(x.key)}
                    label={x.label}
                    unit={unitLabel(x.unit)}
                    was={formatAmount(x.value, x.unit)}
                  />
                </td>
                <td className="px-4 py-2">
                  {x.rules.length > 0 ? (
                    <RuleIds ids={x.rules} settings={s} />
                  ) : (
                    <span className="text-muted-foreground">
                      {t("admin.settings.tolerances.unused")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function PolicyPanel({ settings: s, edit }: { settings: EditableSettings; edit: Editor }) {
  const kind = (k: "min" | "max") => t(`admin.settings.policy.kind.${k}`);
  return (
    <Panel
      title={t("admin.settings.policy.title")}
      subtitle={t("admin.settings.policy.subtitle")}
      testId="settings-policy"
    >
      <h3 className={SUBHEAD}>{t("admin.settings.policy.ratios")}</h3>
      <p className={HELP}>{t("admin.settings.policy.ratiosHelp")}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-[12.5px]">
          <thead>
            <tr className={HEAD}>
              <th className="px-4 py-2 font-medium">{t("admin.settings.policy.ratio")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.policy.acceptable")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.policy.marginal")}</th>
              <th className="px-4 py-2 font-medium">{t("admin.settings.policy.norms")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {s.ratios.map((r) => (
              <tr key={r.key} className="align-top" data-testid={`ratio-${r.key}`}>
                <td className="px-4 py-2">{r.label}</td>
                {(["acceptable", "marginal"] as const).map((f) => (
                  <td key={f} className="px-3 py-2">
                    <NumberSetting
                      edit={edit}
                      field={fieldKey.ratio(r.key, f)}
                      label={`${r.label} · ${t(`admin.settings.policy.${f}`)}`}
                      prefix={kind(r.kind)}
                      unit={unitLabel(r.unit)}
                      was={formatAmount(r[f], r.unit)}
                    />
                  </td>
                ))}
                <td className="px-4 py-2">
                  {r.norms.length > 0 ? (
                    <span className="flex flex-wrap gap-1">
                      {r.norms.map((id) => (
                        <Chip key={id} tone="muted" className="font-mono">
                          {id}
                        </Chip>
                      ))}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className={SUBHEAD}>{t("admin.settings.policy.own")}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-[12.5px]">
          <thead>
            <tr className={HEAD}>
              <th className="px-4 py-2 font-medium">{t("admin.settings.policy.norm")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.policy.threshold")}</th>
            </tr>
          </thead>
          {FAMILIES.map((family) => {
            const norms = s.norms.filter((n) => n.family === family);
            if (norms.length === 0) return null;
            return (
              <tbody key={family} className="divide-y divide-border">
                <tr>
                  <th colSpan={2} className={GROUP}>
                    {t(`policy.family.${family}`)}
                  </th>
                </tr>
                {norms.map((n) => (
                  <tr key={n.id} className="align-top" data-testid={`norm-${n.id}`}>
                    <td className="px-4 py-2">
                      <span className="mr-2 font-mono text-[11.5px] text-muted-foreground">
                        {n.id}
                      </span>
                      {n.label}
                    </td>
                    <td className="px-3 py-2">
                      <NumberSetting
                        edit={edit}
                        field={fieldKey.norm(n.id)}
                        label={`${n.id} ${n.label}`}
                        prefix={kind(n.kind)}
                        unit={unitLabel(n.unit)}
                        was={formatAmount(n.threshold, n.unit)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            );
          })}
        </table>
      </div>
    </Panel>
  );
}

function RulesPanel({ settings: s, edit }: { settings: EditableSettings; edit: Editor }) {
  const areas = [...new Set(s.rules.map((r) => r.area))];
  const severities = SEVERITIES.map((v) => ({ value: v, label: t(`severity.${v}`) }));
  return (
    <Panel
      title={t("admin.settings.rules.title")}
      subtitle={t("admin.settings.rules.subtitle")}
      testId="settings-rules"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-[12.5px]">
          <thead>
            <tr className={HEAD}>
              <th className="px-4 py-2 font-medium">{t("admin.settings.rules.rule")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.rules.runs")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.rules.severity")}</th>
              <th className="px-4 py-2 font-medium">{t("admin.settings.rules.blocks")}</th>
            </tr>
          </thead>
          {areas.map((area) => (
            <tbody key={area} className="divide-y divide-border">
              <tr>
                <th colSpan={4} className={GROUP}>
                  {tOr(`crossVerification.area.${area}.title`, area)}
                </th>
              </tr>
              {s.rules
                .filter((r) => r.area === area)
                .map((r) => (
                  <tr key={r.id} className="align-top" data-testid={`rule-${r.id}`}>
                    <td className="px-4 py-2">
                      <span className="mr-2 font-mono text-[11.5px] text-muted-foreground">
                        {r.id}
                      </span>
                      {r.title}
                    </td>
                    <td className="px-3 py-2">
                      <SwitchSetting
                        edit={edit}
                        field={fieldKey.rule(r.id, "enabled")}
                        label={`${r.id} · ${t("admin.settings.rules.runs")}`}
                        was={
                          r.enabled
                            ? t("admin.settings.rules.enabled")
                            : t("admin.settings.rules.disabled")
                        }
                        on={t("admin.settings.rules.enabled")}
                        off={t("admin.settings.rules.disabled")}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <ChoiceSetting
                        edit={edit}
                        field={fieldKey.rule(r.id, "severity")}
                        label={`${r.id} · ${t("admin.settings.rules.severity")}`}
                        was={t(`severity.${r.severity}`)}
                        options={severities}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <CheckboxSetting
                        edit={edit}
                        field={fieldKey.rule(r.id, "blocking")}
                        label={`${r.id} · ${t("admin.settings.rules.blocks")}`}
                        was={yesNoText(r.blocking)}
                      />
                    </td>
                  </tr>
                ))}
            </tbody>
          ))}
        </table>
      </div>
    </Panel>
  );
}

function MatrixPanel({ settings: s, edit }: { settings: EditableSettings; edit: Editor }) {
  const { authorities, products, deviations, status } = s.matrix;
  const name = (key: string | null | undefined) =>
    key ? (authorities.find((a) => a.key === key)?.label ?? key) : t("admin.settings.matrix.none");
  const options = authorities.map((a) => ({ value: a.key, label: a.label }));
  return (
    <Panel
      title={t("admin.settings.matrix.title")}
      subtitle={t("admin.settings.matrix.subtitle")}
      action={
        status === "provisional" ? (
          <Chip tone="muted">{t("approvingAuthority.provisional")}</Chip>
        ) : undefined
      }
      testId="settings-matrix"
    >
      {products.map((p) => (
        <section key={p.key} data-testid={`matrix-${p.key}`}>
          <h3 className={SUBHEAD}>{p.label}</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-[12.5px]">
              <thead>
                <tr className={HEAD}>
                  <th className="w-24 px-4 py-2 font-medium">{t("admin.settings.matrix.band")}</th>
                  <th className="px-3 py-2 font-medium">{t("admin.settings.matrix.upTo")}</th>
                  <th className="px-4 py-2 font-medium">{t("admin.settings.matrix.authority")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {p.bands.map((b, i) => {
                  const below = i > 0 ? edit.current(fieldKey.band(p.key, i - 1, "up_to_inr")) : 0;
                  return (
                    <tr key={i} className="align-top" data-testid={`band-${p.key}-${i}`}>
                      <td className="px-4 py-2 text-muted-foreground">
                        {t("admin.settings.matrix.bandN", { n: i + 1 })}
                      </td>
                      <td className="px-3 py-2">
                        {typeof b.up_to_inr === "number" ? (
                          <NumberSetting
                            edit={edit}
                            field={fieldKey.band(p.key, i, "up_to_inr")}
                            label={`${p.label} · ${t("admin.settings.matrix.bandN", { n: i + 1 })}`}
                            unit={t("admin.settings.matrix.crore")}
                            was={formatInr(b.up_to_inr)}
                            kind="amount"
                          />
                        ) : (
                          <span className="tabular text-muted-foreground">
                            {t("admin.settings.matrix.above", {
                              amount: formatInr(typeof below === "number" ? below : 0),
                            })}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <ChoiceSetting
                          edit={edit}
                          field={fieldKey.band(p.key, i, "authority")}
                          label={`${p.label} · ${t("admin.settings.matrix.bandN", { n: i + 1 })} · ${t("admin.settings.matrix.authority")}`}
                          was={name(b.authority)}
                          options={options}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <h3 className={SUBHEAD}>{t("admin.settings.matrix.deviations")}</h3>
      <p className={HELP}>{t("admin.settings.matrix.deviationsHelp")}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-[12.5px]">
          <thead>
            <tr className={HEAD}>
              <th className="px-4 py-2 font-medium">{t("admin.settings.matrix.category")}</th>
              <th className="px-3 py-2 font-medium">{t("admin.settings.matrix.levelsAbove")}</th>
              <th className="px-4 py-2 font-medium">{t("admin.settings.matrix.atLeast")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {deviations.map((d) => (
              <tr key={d.category} className="align-top" data-testid={`deviation-${d.category}`}>
                <td className="px-4 py-2">{d.label}</td>
                <td className="px-3 py-2">
                  <NumberSetting
                    edit={edit}
                    field={fieldKey.deviation(d.category, "levels_above")}
                    label={`${d.label} · ${t("admin.settings.matrix.levelsAbove")}`}
                    was={String(d.levels_above)}
                    kind="count"
                  />
                </td>
                <td className="px-4 py-2">
                  <ChoiceSetting
                    edit={edit}
                    field={fieldKey.deviation(d.category, "at_least")}
                    label={`${d.label} · ${t("admin.settings.matrix.atLeast")}`}
                    was={name(d.at_least)}
                    options={[{ value: "", label: t("admin.settings.matrix.none") }, ...options]}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
