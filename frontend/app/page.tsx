import { Nav } from "@/components/landing/nav";
import { Hero } from "@/components/landing/hero";
import { Agents } from "@/components/landing/agents";
import { LiveDemo } from "@/components/landing/demo";
import {
  Architecture,
  Contact,
  Docs,
  ExampleProjects,
  Features,
  Footer,
  HowItWorks,
  Pricing,
} from "@/components/landing/sections";

export default function LandingPage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <LiveDemo />
        <Agents />
        <ExampleProjects />
        <Pricing />
        <Architecture />
        <Docs />
        <Contact />
      </main>
      <Footer />
    </>
  );
}
