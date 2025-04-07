import Link from 'next/link';
import { MessageSquareOff } from 'lucide-react'; 
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

/**
 * Renders a page indicating that the requested conversation was not found
 * or the user does not have permission to view it.
 */
export default function ConversationNotFound() {
  return (
    // Center the content vertically and horizontally
    <div className="flex h-full flex-col items-center justify-center p-4 md:p-6">
      {/* Adjust min-h calculation based on your actual header/nav height if needed */}
      <Card className="w-full max-w-md text-center shadow-lg">
        <CardHeader>
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border bg-secondary">
             <MessageSquareOff className="h-8 w-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-2xl font-semibold">Conversa Indisponível</CardTitle> {/* PT-BR */}
          <CardDescription className="mt-2 text-muted-foreground">

            A conversa que você procura não foi encontrada. Isso pode ter acontecido porque:
            <ul className="mt-2 list-inside list-disc text-left text-sm">
              <li>O link está incorreto ou desatualizado.</li>
              <li>A conversa foi arquivada ou excluída.</li>
              <li>Você não tem permissão para acessá-la.</li>
            </ul>
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pt-2">
          <Button size="lg">
            <Link href="/dashboard/conversations">Ver Minhas Conversas</Link> {/* PT-BR */}
          </Button>
          <Button variant="outline">
            <Link href="/dashboard">Ir para o Painel Principal</Link> {/* PT-BR */}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}