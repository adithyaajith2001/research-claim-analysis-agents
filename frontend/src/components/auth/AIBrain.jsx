import { FaBrain } from "react-icons/fa";

function AIBrain() {
  return (
    <div className="ai-section">

      <div className="paper paper1">Paper 1</div>
      <div className="paper paper2">Paper 2</div>
      <div className="paper paper3">Paper 3</div>

      <div className="brain-circle">
        <FaBrain />
      </div>

      <div className="agent left1">Retrieval</div>
      <div className="agent left2">Extraction</div>

      <div className="agent right1">Verification</div>
      <div className="agent right2">Scoring</div>

    </div>
  );
}

export default AIBrain;