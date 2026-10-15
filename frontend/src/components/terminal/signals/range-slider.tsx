import * as SliderPrimitive from "@radix-ui/react-slider";

import { InfoTip } from "@/components/terminal/kit";

/** Two-thumb (or one-thumb) slider with a label and live value read-out. */
export function RangeSlider({
  label,
  info,
  min,
  max,
  step,
  value,
  onChange,
  format,
  className,
}: {
  label: string;
  info: string;
  min: number;
  max: number;
  step: number;
  value: number[];
  onChange: (v: number[]) => void;
  format: (n: number) => string;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px] uppercase tracking-label text-muted-foreground">
        <span className="flex items-center gap-1">
          {label}
          <InfoTip text={info} />
        </span>
        <span className="num normal-case tracking-normal text-foreground">
          {value.map(format).join(" – ")}
        </span>
      </div>
      <SliderPrimitive.Root
        min={min}
        max={max}
        step={step}
        value={value}
        onValueChange={onChange}
        minStepsBetweenThumbs={0}
        className="relative flex h-4 w-full touch-none select-none items-center"
      >
        <SliderPrimitive.Track className="relative h-1 w-full grow overflow-hidden rounded-full bg-surface">
          <SliderPrimitive.Range className="absolute h-full bg-primary" />
        </SliderPrimitive.Track>
        {value.map((_, i) => (
          <SliderPrimitive.Thumb
            key={i}
            aria-label={`${label} ${value.length > 1 ? (i === 0 ? "minimum" : "maximum") : "value"}`}
            className="block size-3.5 rounded-full border border-primary bg-paper shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        ))}
      </SliderPrimitive.Root>
    </div>
  );
}
