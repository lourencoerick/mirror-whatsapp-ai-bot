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
            <div className="bg-secondary text-foreground w-full px-5 sm:px-10 lg:px-30 mb-0 ">
                {children}
            </div>
            <CTASection bgColor="bg-background" hideLambda={true} buttonFontSize="text-md md:text-lg"/>
        </>
    );
}

