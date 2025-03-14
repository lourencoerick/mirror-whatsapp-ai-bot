import NavBar from "@/components/ui/home/navbar";
import CTASection from "@/components/ui/home/cta-section";
import "@/app/globals.css";

export default function HomeLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <>
            <NavBar />
            <div className="bg-background text-foreground min-h-1/2 w-full px-10 lg:px-30 mb-1 ">
                {children}
            </div>
            <CTASection bgColor="bg-secondary" hideLambda={true} buttonFontSize="text-md md:text-lg"/>
        </>
    );
}

