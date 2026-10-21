import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Cam, CamTemplate, CamTemplateSection, CamTemplates } from "@/api/types";
import { api } from "@/api/client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { useCamChange, useCamTemplates, useCreateCamTemplate } from "@/domain/findings";
import { cn } from "@/lib/utils";

// CAM templates (F-23; FRD decision C.4-12): the layout this appraisal's memo follows, chosen from
// the default and the templates analysts have made, and the builder for a new one. A template only
// arranges what the engine drafts: each section draws on parts of the file (each part in one
// section at most) or is left blank for the analyst to write; the risk assessment and the
// recommendation always close the memo. A template is never edited in place.
//
// Test ids: cam-template (the picker: cam-template-select, cam-template-new), cam-template-dialog
// (cam-template-name, cam-template-description, cam-template-start, a cam-template-section each
// with cam-template-section-title, cam-template-section-purpose, cam-template-part (data-part,
// aria-pressed), cam-template-up, cam-template-down, cam-template-remove; cam-template-add,
// cam-template-closing, cam-template-use, cam-template-save, cam-template-error)

const field =
  "w-full rounded border border-border bg-surface px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

/** The picker at the head of the sections list. */
export function TemplatePicker({ caseId, m }: { caseId: string; m: Cam }) {
  const list = useCamTemplates();
  const choose = useCamChange(caseId, (templateId: string) =>
    api.chooseCamTemplate(caseId, templateId),
  );
  const [building, setBuilding] = useState(false);
  const templates = list.data?.templates ?? [];
  return (
    <div className="space-y-1.5" data-testid="cam-template">
      <label className="block text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {t("outputs.templates.label")}
        <select
          value={m.template_id ?? "default"}
          onChange={(e) => choose.mutate(e.target.value)}
          disabled={choose.isPending || list.isLoading}
          className={cn(field, "mt-1 py-1.5 normal-case tracking-normal")}
          data-testid="cam-template-select"
        >
          {templates.length === 0 && (
            <option value={m.template_id ?? "default"}>{m.template_name || "…"}</option>
          )}
          {templates.map((tpl) => (
            <option key={tpl.id} value={tpl.id}>
              {t("outputs.templates.option", { name: tpl.name, n: tpl.sections.length + 2 })}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={() => setBuilding(true)}
        disabled={!list.data}
        className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline disabled:opacity-50"
        data-testid="cam-template-new"
      >
        <Plus className="h-3.5 w-3.5" aria-hidden />
        {t("outputs.templates.new")}
      </button>
      {choose.error && (
        <p className="text-[11.5px] text-destructive">{(choose.error as Error).message}</p>
      )}
      {building && list.data && (
        <TemplateBuilder
          caseId={caseId}
          catalogue={list.data}
          start={templates.find((x) => x.id === m.template_id) ?? templates[0]!}
          onClose={() => setBuilding(false)}
        />
      )}
    </div>
  );
}

type Draft = { key: number; title: string; purpose: string; parts: string[] };

let nextKey = 1;
const fromTemplate = (tpl: CamTemplate): Draft[] =>
  tpl.sections.map((s) => ({
    key: nextKey++,
    title: s.title,
    purpose: s.purpose ?? "",
    parts: [...(s.parts ?? [])],
  }));

/** The builder: a name, then the sections in order, each with its parts or left blank. */
function TemplateBuilder({
  caseId,
  catalogue,
  start,
  onClose,
}: {
  caseId: string;
  catalogue: CamTemplates;
  start: CamTemplate;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [from, setFrom] = useState(start.id);
  const [sections, setSections] = useState<Draft[]>(() => fromTemplate(start));
  const [use, setUse] = useState(true);
  const create = useCreateCamTemplate();
  const choose = useCamChange(caseId, (templateId: string) =>
    api.chooseCamTemplate(caseId, templateId),
  );
  const partTitle = (kind: string) => catalogue.parts.find((p) => p.kind === kind)?.title ?? kind;
  const owner = (kind: string) => sections.find((s) => s.parts.includes(kind))?.key;

  const update = (key: number, change: Partial<Draft>) =>
    setSections((all) => all.map((s) => (s.key === key ? { ...s, ...change } : s)));
  const move = (i: number, by: -1 | 1) =>
    setSections((all) => {
      const next = [...all];
      const [s] = next.splice(i, 1);
      next.splice(i + by, 0, s!);
      return next;
    });
  const togglePart = (s: Draft, kind: string) =>
    update(s.key, {
      parts: s.parts.includes(kind) ? s.parts.filter((k) => k !== kind) : [...s.parts, kind],
    });

  const ready =
    name.trim().length >= 3 && sections.length > 0 && sections.every((s) => s.title.trim());
  const save = () => {
    const body = {
      name: name.trim(),
      description: description.trim(),
      sections: sections.map((s): CamTemplateSection => ({
        id: "",
        title: s.title.trim(),
        purpose: s.purpose.trim() || null,
        parts: s.parts,
      })),
    };
    create.mutate(body, {
      onSuccess: (made) => {
        if (use) choose.mutate(made.id, { onSuccess: onClose });
        else onClose();
      },
    });
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-3xl overflow-y-auto"
        data-testid="cam-template-dialog"
      >
        <DialogHeader>
          <DialogTitle>{t("outputs.templates.builderTitle")}</DialogTitle>
          <DialogDescription>{t("outputs.templates.builderHint")}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="text-[12px] text-muted-foreground">{t("outputs.templates.name")}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("outputs.templates.namePlaceholder")}
              className={cn(field, "mt-1")}
              data-testid="cam-template-name"
            />
          </label>
          <label className="block">
            <span className="text-[12px] text-muted-foreground">
              {t("outputs.templates.start")}
            </span>
            <select
              value={from}
              onChange={(e) => {
                const tpl = catalogue.templates.find((x) => x.id === e.target.value);
                setFrom(e.target.value);
                setSections(tpl ? fromTemplate(tpl) : []);
              }}
              className={cn(field, "mt-1")}
              data-testid="cam-template-start"
            >
              {catalogue.templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="text-[12px] text-muted-foreground">
              {t("outputs.templates.description")}
            </span>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("outputs.templates.descriptionPlaceholder")}
              className={cn(field, "mt-1")}
              data-testid="cam-template-description"
            />
          </label>
        </div>

        <ol className="space-y-2.5">
          {sections.map((s, i) => (
            <li
              key={s.key}
              className="rounded border border-border bg-surface-muted/30 p-3"
              data-testid="cam-template-section"
            >
              <div className="flex items-start gap-2">
                <span className="tabular mt-2 w-5 shrink-0 text-[12px] text-muted-foreground">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1 space-y-2">
                  <input
                    value={s.title}
                    onChange={(e) => update(s.key, { title: e.target.value })}
                    placeholder={t("outputs.templates.sectionTitle")}
                    className={field}
                    data-testid="cam-template-section-title"
                  />
                  <input
                    value={s.purpose}
                    onChange={(e) => update(s.key, { purpose: e.target.value })}
                    placeholder={t("outputs.templates.sectionPurpose")}
                    className={cn(field, "text-[12.5px]")}
                    data-testid="cam-template-section-purpose"
                  />
                  <div className="flex flex-wrap gap-1.5">
                    {catalogue.parts.map((p) => {
                      const on = s.parts.includes(p.kind);
                      const elsewhere = !on && owner(p.kind) !== undefined;
                      return (
                        <button
                          key={p.kind}
                          type="button"
                          onClick={() => togglePart(s, p.kind)}
                          disabled={elsewhere}
                          aria-pressed={on}
                          title={elsewhere ? t("outputs.templates.partElsewhere") : undefined}
                          className={cn(
                            "rounded-full border px-2.5 py-0.5 text-[11.5px] transition-colors",
                            on
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-surface text-muted-foreground hover:text-foreground",
                            elsewhere && "cursor-not-allowed opacity-40",
                          )}
                          data-testid="cam-template-part"
                          data-part={p.kind}
                        >
                          {partTitle(p.kind)}
                        </button>
                      );
                    })}
                  </div>
                  {s.parts.length === 0 && (
                    <p className="text-[11.5px] text-muted-foreground">
                      {t("outputs.templates.blank")}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <IconButton
                    label={t("outputs.templates.up")}
                    onClick={() => move(i, -1)}
                    disabled={i === 0}
                    testId="cam-template-up"
                  >
                    <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                  </IconButton>
                  <IconButton
                    label={t("outputs.templates.down")}
                    onClick={() => move(i, 1)}
                    disabled={i === sections.length - 1}
                    testId="cam-template-down"
                  >
                    <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                  </IconButton>
                  <IconButton
                    label={t("outputs.templates.remove")}
                    onClick={() => setSections((all) => all.filter((x) => x.key !== s.key))}
                    testId="cam-template-remove"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </IconButton>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <button
          type="button"
          onClick={() =>
            setSections((all) => [...all, { key: nextKey++, title: "", purpose: "", parts: [] }])
          }
          disabled={sections.length >= 15}
          className="inline-flex items-center gap-1 self-start rounded border border-dashed border-border px-3 py-1.5 text-[12.5px] font-medium text-foreground hover:bg-surface-muted disabled:opacity-50"
          data-testid="cam-template-add"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          {t("outputs.templates.add")}
        </button>
        <p className="text-[12px] text-muted-foreground" data-testid="cam-template-closing">
          {t("outputs.templates.closing", {
            sections: catalogue.closing.join(" and "),
            first: sections.length + 1,
          })}
        </p>

        <DialogFooter className="flex-wrap items-center gap-3 sm:justify-between">
          <label className="inline-flex items-center gap-2 text-[12.5px]">
            <input
              type="checkbox"
              checked={use}
              onChange={(e) => setUse(e.target.checked)}
              data-testid="cam-template-use"
            />
            {t("outputs.templates.use")}
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="h-9 rounded border border-border px-4 text-[13px] font-medium"
            >
              {t("outputs.templates.cancel")}
            </button>
            <button
              type="button"
              onClick={save}
              disabled={!ready || create.isPending || choose.isPending}
              className="h-9 rounded bg-primary px-4 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
              data-testid="cam-template-save"
            >
              {t("outputs.templates.save")}
            </button>
          </div>
        </DialogFooter>
        {(create.error || choose.error) && (
          <p className="text-[12px] text-destructive" data-testid="cam-template-error">
            {((create.error || choose.error) as Error).message}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function IconButton({
  children,
  label,
  onClick,
  disabled,
  testId,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="rounded border border-border bg-surface p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
      data-testid={testId}
    >
      {children}
    </button>
  );
}
