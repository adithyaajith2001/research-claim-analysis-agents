import React from "react";
import {
  FaRobot,
  FaShieldAlt,
  FaChartLine
} from "react-icons/fa";

import FeatureCard from "./FeatureCard";

const FeatureCards = () => {
  return (
    <section className="feature-list">

      <FeatureCard
        icon={<FaRobot />}
        title="Multi-Agent AI"
        description="Multiple AI agents collaborate to analyze research papers."
      />

      <FeatureCard
        icon={<FaShieldAlt />}
        title="Claim Verification"
        description="Supporting and contradicting evidence are compared automatically."
      />

      <FeatureCard
        icon={<FaChartLine />}
        title="Confidence Score"
        description="Generates an explainable confidence score for every claim."
      />

    </section>
  );
};

export default FeatureCards;