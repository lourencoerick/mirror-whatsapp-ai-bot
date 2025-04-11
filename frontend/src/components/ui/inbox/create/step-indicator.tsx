// src/app/dashboard/inboxes/new/components/StepIndicator.tsx
/**
 * @fileoverview Component to display steps in the inbox creation wizard.
 */
import React from 'react';
import { cn } from "@/lib/utils"; // Assuming you have cn from shadcn/ui
import { Check } from 'lucide-react';

interface Step {
    id: number;
    name: string;
    description?: string; // Optional description
}

interface StepIndicatorProps {
    steps: Step[];
    currentStepId: number;
    className?: string;
}

/**
 * Displays a vertical list of steps, highlighting the current and completed steps.
 *
 * @component
 * @param {StepIndicatorProps} props - Component props.
 * @returns {React.ReactElement} The step indicator component.
 */
export const StepIndicator: React.FC<StepIndicatorProps> = ({
    steps,
    currentStepId,
    className,
}) => {
    return (
        <nav aria-label="Progress" className={cn("space-y-4", className)}>
            <ol role="list" className="space-y-4">
                {steps.map((step, stepIdx) => {
                    const isCompleted = step.id < currentStepId;
                    const isCurrent = step.id === currentStepId;

                    return (
                        <li key={step.id} className="relative flex items-start">
                             {/* Connector Line (optional, simple version omits it) */}
                             {stepIdx !== steps.length - 1 && (
                                <div className="absolute left-4 top-4 -ml-px mt-0.5 h-full w-0.5 bg-border" aria-hidden="true" />
                             )}

                             {/* Step Circle/Icon */}
                            <div className="relative flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full">
                                {isCompleted ? (
                                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary">
                                        <Check className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
                                    </span>
                                ) : isCurrent ? (
                                    <span className="relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-primary-foreground">
                                         <span className="h-2 w-2 rounded-full bg-primary" aria-hidden="true" />
                                    </span>
                                ) : (
                                    <span className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-border bg-muted">
                                         <span className="h-2 w-2 rounded-full bg-muted-foreground/50" aria-hidden="true" />
                                    </span>
                                )}
                             </div>

                             {/* Step Name & Description */}
                            <div className="ml-4 min-w-0 flex-grow">
                                <span className={cn(
                                    "text-sm font-medium",
                                    isCurrent ? 'text-primary' : isCompleted ? 'text-foreground' : 'text-muted-foreground'
                                )}>
                                    {step.name}
                                </span>
                                {step.description && (
                                    <p className={cn(
                                        "text-xs",
                                        isCurrent || isCompleted ? 'text-muted-foreground' : 'text-muted-foreground/70'
                                    )}>
                                        {step.description}
                                    </p>
                                )}
                            </div>
                        </li>
                    );
                })}
            </ol>
        </nav>
    );
};