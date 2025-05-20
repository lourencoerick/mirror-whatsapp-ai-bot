/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/ui/calendar.tsx
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";
import {
  DayPicker,
  type DayPickerProps,
  type ChevronProps as RDPChevronProps,
} from "react-day-picker";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type CalendarProps = DayPickerProps;
/**
 * @typedef {import("react-day-picker").DayPickerProps} DayPickerProps
 */

/**
 * Props for the Calendar component.
 * Extends all props from `react-day-picker`'s `DayPicker`.
 * @typedef {React.ComponentProps<typeof DayPicker>} CalendarProps
 */

/**
 * A customizable calendar component based on `react-day-picker`.
 *
 * This component wraps `react-day-picker` and provides default styling.
 * It includes basic internal state management for uncontrolled single-date selection.
 *
 * @example
 * // Uncontrolled single date selection
 * <Calendar />
 *
 * @example
 * // Controlled single date selection
 * const [date, setDate] = React.useState<Date | undefined>(new Date());
 * <Calendar mode="single" selected={date} onSelect={setDate} />
 *
 * @param {CalendarProps} props - The props for the Calendar component.
 * @param {string} [props.className] - Additional class names for the calendar container.
 * @param {object} [props.classNames] - Custom class names for specific parts of the calendar.
 * @param {boolean} [props.showOutsideDays=true] - Whether to show days from previous/next months.
 * All other props are passed directly to `react-day-picker`'s `DayPicker` component.
 */
export function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  // Internal state for handling uncontrolled single date selection.
  // Initialized to undefined, meaning no date is selected by default.
  const [internalSelected, setInternalSelected] = React.useState<
    Date | undefined
  >();

  // Determine if the component is controlled or uncontrolled for selection.
  // We use `(props as any).selected` here because `selected` is not present on all
  // types within the `DayPickerProps` union, causing a TypeScript error otherwise.
  // This assumes that if `selected` is provided, the component is controlled.
  const isControlled = (props as any).selected !== undefined;

  // Determine the selected date to pass to DayPicker.
  // If controlled, use `props.selected`. Otherwise, use internal state.
  // `(props as any).selected` is used for the same reason as above.
  const selectedDate = isControlled
    ? (props as any).selected
    : internalSelected;

  // Determine the onSelect handler to pass to DayPicker.
  // If controlled, use `props.onSelect`. Otherwise, use the internal state setter.
  // `(props as any).onSelect` is used for the same reason as above.
  // WARNING: This internal `setInternalSelected` is only suitable for single date selection.
  // If used in uncontrolled mode with `mode="multiple"` or `mode="range"`, this will lead to
  // incorrect behavior as `setInternalSelected` expects a single `Date` or `undefined`.
  const handleSelect = isControlled
    ? (props as any).onSelect
    : setInternalSelected;

  return (
    <DayPicker
      mode="single"
      showOutsideDays={showOutsideDays}
      className={cn("p-6", className)}
      // Pass down the determined selected date and select handler.
      // These will override `selected` and `onSelect` if they were part of `...props`.
      selected={selectedDate}
      onSelect={handleSelect}
      classNames={{
        months: "flex flex-col sm:flex-row gap-4",
        month: "flex flex-col gap-4",
        // caption is relative to position nav buttons absolutely
        caption: "flex justify-center items-center pt-1 relative w-full",
        caption_label: "text-sm font-medium",
        nav: "flex items-center justify-center", // Nav container
        button: cn(
          // Default button style for nav buttons
          buttonVariants({ variant: "outline" }),
          "size-7 bg-transparent p-0 opacity-50 hover:opacity-100"
        ),
        button_previous: "absolute left-1", // Previous month button
        button_next: "absolute right-1", // Next month button
        table: "w-full border-collapse mt-2", // Calendar grid
        head_row: "flex",
        head_cell:
          "text-muted-foreground rounded-md w-9 text-[0.8rem] font-normal",
        row: "flex w-full mt-2",
        day: cn(
          // Individual day cell container
          "size-9 p-0 text-center text-sm relative focus-within:z-20",
          "[&:has([aria-selected])]:rounded-md [&:has([aria-selected])]:bg-accent/50",
          // Apply specific styles for range selection if mode is "range"
          (props as any).mode === "range"
            ? "[&:has(>.range_end)]:rounded-r-md [&:has(>.range_start)]:rounded-l-md"
            : ""
        ),
        day_button: cn(
          // Clickable button within each day cell
          buttonVariants({ variant: "ghost" }),
          "size-9 p-0 font-normal aria-selected:opacity-100"
        ),
        // Modifiers for day states
        selected:
          "!bg-primary !text-primary-foreground hover:!bg-primary focus:!bg-primary rounded-md",
        today: "ring-1 ring-accent text-accent-foreground",
        outside:
          "text-muted-foreground opacity-50 aria-selected:bg-accent/30 aria-selected:text-muted-foreground",
        disabled: "text-muted-foreground opacity-50",
        hidden: "invisible",
        range_start: "!bg-primary !text-primary-foreground rounded-l-md",
        range_end: "!bg-primary !text-primary-foreground rounded-r-md",
        range_middle:
          "aria-selected:!bg-accent aria-selected:!text-accent-foreground",
        // Allow consumer to override any classNames
        ...classNames,
      }}
      components={{
        Chevron: ({
          orientation,
          className: chevronClassName,
          ...rest
        }: RDPChevronProps) =>
          orientation === "left" ? (
            <ChevronLeft className={cn("size-6", chevronClassName)} {...rest} />
          ) : (
            <ChevronRight
              className={cn("size-6", chevronClassName)}
              {...rest}
            />
          ),
      }}
      // Spread the rest of the props to DayPicker.
      // This ensures that `mode`, and other DayPicker features are passed through.
      // `selected` and `onSelect` from `...props` are effectively overridden by the ones we explicitly set above.
      {...props}
    />
  );
}

Calendar.displayName = "Calendar";
