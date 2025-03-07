import React from 'react';

interface StepCardProps {
    step: number;
    title: string;
    titleSize: string;
    icon?: React.ReactNode;
    description?: React.ReactNode;
    descriptionMargin?: string;
    children?: React.ReactNode;
}

export default function StepCard({ step, title, titleSize = "text-2xl", icon, description, descriptionMargin = "mt-10" }: StepCardProps) {
    return (
        <div className="h-80 md:h-80 w-full md:w-90 bg-accent text-card-foreground p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
            <div className="flex flex-row items-center justify-start gap-4 mb-4">
                <div className="w-10 h-10 border-2 rounded-full bg-card flex items-center justify-center text-card-primary font-bold text-xl flex-none">
                    {step}
                </div>
                <h3 className={`${titleSize} font-bold`}>{title}</h3>
            </div>
            <div>
                {icon && description && <p className={`text-base ${descriptionMargin} text-md md:text-md leading-relaxed`}>{icon} {description}</p>}
            </div>
        </div>
    );
}

