import NavBar from "@/components/ui/home/navbar";
import CTASection from "@/components/ui/home/cta-section";

export default function HomeLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <>
            <NavBar />
            <div className="bg-background text-foreground w-full px-10 lg:px-30">
                {children}
            </div>
            <CTASection bgColor="bg-secondary" hideLambda={true}/>
        </>
    );
}

