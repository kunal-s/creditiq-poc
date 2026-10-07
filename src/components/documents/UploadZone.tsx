import { useRef, useState } from "react";
import { Camera, FileUp, UploadCloud } from "lucide-react";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

/** Accepted on the picker; the engine decides the true type from content (F-05.3). */
const ACCEPT =
  ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.xlsx,.xls,.csv,.docx,.zip,application/pdf,image/*,application/zip";

/** Drop zone and pickers for files, several files or ZIP archives (F-05.1),
 * with a camera input for phones (F-06.1). */
export function UploadZone({
  onFiles,
  busy,
  disabled,
  compact,
}: {
  onFiles: (files: File[]) => void;
  busy?: boolean;
  disabled?: boolean;
  compact?: boolean;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const off = Boolean(busy || disabled);

  const take = (list: FileList | null) => {
    const files = list ? Array.from(list) : [];
    if (files.length > 0) onFiles(files);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!off) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!off) take(e.dataTransfer.files);
      }}
      data-testid="upload-zone"
      className={cn(
        "flex flex-col items-center justify-center rounded border-2 border-dashed border-primary/30 bg-primary/5 px-4 text-center transition-colors",
        compact ? "py-4" : "py-10",
        dragging && "border-primary bg-primary/10",
        off && "opacity-60",
      )}
    >
      <UploadCloud className={cn("text-primary", compact ? "h-5 w-5" : "h-6 w-6")} />
      <p className="mt-2 text-[13px] font-medium text-foreground">
        {busy ? t("upload.busy") : t("upload.drop")}
      </p>
      <p className="mt-0.5 text-[11.5px] text-muted-foreground">{t("upload.formats")}</p>
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        data-testid="upload-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        data-testid="camera-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      <div className={cn("flex flex-wrap justify-center gap-2", compact ? "mt-2.5" : "mt-3")}>
        <button
          type="button"
          disabled={off}
          onClick={() => fileInput.current?.click()}
          className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <FileUp className="h-3.5 w-3.5" /> {t("upload.browse")}
        </button>
        <button
          type="button"
          disabled={off}
          onClick={() => cameraInput.current?.click()}
          className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted disabled:opacity-50 md:hidden"
        >
          <Camera className="h-3.5 w-3.5" /> {t("upload.camera")}
        </button>
      </div>
    </div>
  );
}
