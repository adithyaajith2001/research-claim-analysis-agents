# AI-Powered Research Claim Analysis

An AI-powered web application designed to analyze research claims, retrieve supporting evidence, identify contradicting evidence, and provide an interpretable confidence assessment.

## Project Overview

The Research Claim Analysis system helps users evaluate scientific and research-related claims by combining automated literature analysis, evidence verification, and visualization.

The frontend provides an interactive interface where users can enter a research claim or topic and view the analysis results through a structured dashboard.

## Key Features

- AI-powered research claim analysis
- Research query input
- Literature search workflow
- Research paper retrieval
- Claim extraction
- Evidence verification
- Confidence scoring
- Supporting and contradicting evidence
- Evidence visualization
- Citation network visualization
- Analysis pipeline visualization
- Interactive dashboard
- User authentication
- Google authentication
- Responsive user interface

## Frontend Technologies

- React.js
- Vite
- JavaScript
- HTML5
- CSS3
- Firebase Authentication
- D3.js
- React Router

## Project Structure

```text
frontend/
│
├── public/
│
├── src/
│   ├── assets/
│   │
│   ├── components/
│   │   ├── auth/
│   │   ├── common/
│   │   ├── dashboard/
│   │   ├── evidence/
│   │   ├── layout/
│   │   ├── loading/
│   │   ├── query/
│   │   └── results/
│   │
│   ├── context/
│   ├── mocks/
│   ├── pages/
│   ├── routes/
│   ├── services/
│   ├── styles/
│   ├── visualizations/
│   │
│   ├── App.jsx
│   ├── firebase.js
│   ├── index.css
│   └── main.jsx
│
├── .gitignore
├── index.html
├── package.json
├── package-lock.json
└── vite.config.js