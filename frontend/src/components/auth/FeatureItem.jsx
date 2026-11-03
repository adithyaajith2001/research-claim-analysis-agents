function FeatureItem({ icon, title, description }) {
  return (
    <div className="feature-item">

      <div className="feature-icon">
        {icon}
      </div>

      <div>

        <h3>{title}</h3>

        <p>{description}</p>

      </div>

    </div>
  );
}

export default FeatureItem;