// app/dashboard/settings/page.tsx
'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import { getMyBotAgent } from '@/lib/api/bot-agent';
import { getCompanyProfile } from '@/lib/api/company-profile';
import { components } from '@/types/api';
import { useCallback, useEffect, useState } from 'react';

import { BotAgentForm } from './_components/bot-agent-form'; // Importar o novo formulário
import { CompanyProfileForm } from './_components/company-profile-form';
type CompanyProfileData = components['schemas']['CompanyProfileSchema-Output'];
type BotAgentData = components['schemas']['BotAgentRead'];

export default function SettingsPage() {
  const [profileData, setProfileData] = useState<CompanyProfileData | null | undefined>(undefined);
  const [agentData, setAgentData] = useState<BotAgentData | null | undefined>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetcher = useAuthenticatedFetch();

  const fetchData = useCallback(async () => {
    // ... (lógica fetchData como antes) ...
    if (!fetcher) return;
    setIsLoading(true); setError(null);
    try {
      const [profileResult, agentResult] = await Promise.all([
        getCompanyProfile(fetcher), getMyBotAgent(fetcher)
      ]);
      setProfileData(profileResult); setAgentData(agentResult);
    } catch (err: any) {
      console.error("Failed to load settings data:", err);
      setError(err.message || "Failed to load settings.");
      setProfileData(null); setAgentData(null);
    } finally { setIsLoading(false); }
  }, [fetcher]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Callback para atualizar o estado do perfil
  const handleProfileUpdate = useCallback((updatedProfile: CompanyProfileData) => {
    setProfileData(updatedProfile);
  }, []);

   // Callback para atualizar o estado do agente
   const handleAgentUpdate = useCallback((updatedAgent: BotAgentData) => {
    setAgentData(updatedAgent);
  }, []);

  const renderLoading = () => (
    <div className="space-y-4 p-4">
      <Skeleton className="h-8 w-1/4" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );

  const renderError = () => (
     <div className="p-4 text-red-600 bg-red-100 border border-red-400 rounded-md">
        Error: {error}
     </div>
  );

  return (
    <div className="container mx-auto p-4 md:p-6">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      {isLoading ? renderLoading() : error ? renderError() : (
        <Tabs defaultValue="profile" className="w-full">
          <TabsList className="grid w-full grid-cols-2 md:w-[400px]">
            <TabsTrigger value="profile">Company Profile</TabsTrigger>
            <TabsTrigger value="agent">AI Seller</TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="mt-4">
            <CompanyProfileForm
              initialData={profileData}
              fetcher={fetcher!}
              onProfileUpdate={handleProfileUpdate}
            />
            {/* TODO: Adicionar CompanyResearchTrigger e lógica de polling aqui */}
          </TabsContent>

          <TabsContent value="agent" className="mt-4">
             {/* Renderizar o formulário do agente */}
             <BotAgentForm
                initialAgentData={agentData}
                fetcher={fetcher!}
                onAgentUpdate={handleAgentUpdate}
             />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}