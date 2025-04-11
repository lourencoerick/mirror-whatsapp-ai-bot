// src/app/dashboard/inboxes/new/components/ChooseChannelStep.tsx
/**
 * @fileoverview Step 1 Component for selecting the Inbox channel type.
 * Displays options like WhatsApp Evolution API and WhatsApp Cloud API.
 */
import React from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
// Consider adding specific icons if available
import { IconServer, IconCloud } from '@tabler/icons-react';

// Channel options definition
const channelOptions = [
    {
        id: 'whatsapp_evolution_api',
        name: 'WhatsApp (Evolution API)',
        description: 'Conecte via Evolution API auto-hospedada (Requer escanear QR code).',
        icon: IconServer,
    },
    {
        id: 'whatsapp_cloud_api',
        name: 'WhatsApp (API Oficial Cloud)',
        description: 'Conecte via API oficial Cloud da Meta (Requer configuração de App Meta).',
        icon: IconCloud,
    },
];

interface ChooseChannelStepProps {
    /** Function called when a channel is selected, passing the channel type ID. */
    onSelectChannel: (channelTypeId: string) => void;
    stepTitle: string;
    stepDescription: string;
}

/**
 * Renders clickable cards to select the desired communication channel.
 * This is typically the first step in the Inbox creation wizard.
 *
 * @component
 * @param {ChooseChannelStepProps} props - Component props.
 * @returns {React.ReactElement} The channel selection component.
 */
export const ChooseChannelStep: React.FC<ChooseChannelStepProps> = ({
    onSelectChannel,
    stepTitle,
    stepDescription
}) => {
    return (
        <div className="space-y-6">
            {/* Step Header */}
            <CardHeader className="p-0 mb-2 md:mb-4">
                 <CardTitle className="text-xl md:text-2xl">{stepTitle}</CardTitle>
                 <CardDescription>{stepDescription}</CardDescription>
            </CardHeader>

            {/* Grid with Channel Options */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                {channelOptions.map((channel) => (
                    <Card
                        key={channel.id}
                        onClick={() => onSelectChannel(channel.id)}
                        className="cursor-pointer hover:border-primary hover:shadow-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-all duration-150 ease-in-out" // Added focus-visible
                        role="button"
                        tabIndex={0} // Allows keyboard focus
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectChannel(channel.id); }}} // Allows keyboard selection
                        aria-label={`Selecionar canal ${channel.name}`}
                    >
                        <CardHeader className="flex flex-row items-center gap-3 md:gap-4 pb-2 pt-4 px-4 md:px-5">
                            {channel.icon && <channel.icon className="h-7 w-7 md:h-8 md:w-8 text-primary flex-shrink-0" />}
                            <CardTitle className="text-base md:text-lg">{channel.name}</CardTitle>
                        </CardHeader>
                        <CardContent className="pb-4 px-4 md:px-5">
                            <p className="text-xs md:text-sm text-muted-foreground">{channel.description}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};