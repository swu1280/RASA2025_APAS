## AI-Augmented Policy Advisory System（APAS）：A showcase of Sino-US Trade Disputes under WTO Framework 


### 1. Introduction

   In the modern process of policy-making and research, every stage—from problem identification and background analysis to forecasting, evaluation, and the formulation of policy recommendations—reflects a highly structured knowledge system and rigorous logical reasoning. This systemic and logical nature provides a natural foundation for the deep integration of artificial intelligence and policy research. In particular, logic-driven dialogue systems such as RASA have, in recent years, demonstrated strong capabilities in dialogue flow control, conditional reasoning, and state tracking, making them ideal platforms for building policy support systems and expert advisory dialogue agents.

### 2. Goal and Core Functions

   This 48-hour demo implements knowledge network integration and automated story generation by building a multi-layered knowledge system on U.S.-China trade disputes using Mind Maps and Knowledge Graphs. It enables rapid and systematic knowledge structuring, automatically generates semantic relationships between nodes, and produces stories.yml and rules.yml files required by RASA. This significantly reduces manual configuration, enables automated dialogue flow construction and logic optimization, and supports dynamic knowledge updates and multi-turn dialogue path refinement.

   In future, by integrating conversational language AI models such as ChatGPT, the system will support Tariff Policy Analysis, WTO Dispute Resolution, Industry Impact Assessment, Business Strategy Recommendations, and Future Policy Predictions.

### 3. Innovations

#### 1) Knowledge-Driven Dialogue Flow Generation

   The system enables direct import of structured knowledge from mind maps or knowledge graphs and automatically generates stories.yml files for RASA. This greatly reduces the cost of manually crafting dialogue logic. By identifying semantic nodes and reasoning over knowledge relationships, the system dynamically constructs multi-turn dialogue flows, making it highly suitable for complex policy topics.
    
#### 2) Bidirectional Mapping Between Knowledge Graphs and Dialogue Rules

  Each dialogue story node corresponds to a concept or policy event within the knowledge network and can automatically generate reverse mappings into rules.yml. This allows for automated categorization and logic path generation, supporting modular reuse and deployment across various international policy advisory scenarios.

#### 3) Multi-source Heterogeneous Knowledge Integration with Semantic-Enhanced Retrieval

   The system integrates structured API sources (e.g., WTO, IMF, USTR, MOFCOM) with local embedded knowledge bases (e.g., FAISS / ChromaDB) to form a hybrid “real-time + local” retrieval system. It supports natural language question parsing, policy document retrieval, and semantic summarization, significantly enhancing the knowledge depth and real-time responsiveness of AI-driven policy advisory.


### 4. Innovations  
1) **Set Up Environment:**
   - In the codespace, open the `.env` file from this repo and add your license key and ChatGPT API key.
     ```
     RASA_PRO_LICENSE='your_rasa_pro_license_key_here'
     OPENAI_API_KEY='ChatGPT_API_keykey_here'
     ```
   - Set this environment variables by running 
     ```
     source .env
     ```
   - Activate your python environment by running
     ```
     source .venv/bin/activate
     ```
   - Find the requirements.txt and Run the install command
     ```
     pip install -r requirements.txt
     ```

2) Creat your mindmap (.xmind) and data set or use the files included in folder MindMap and WTO.

   ![演示图](MindMap/US-China%20WTO%20Dispute%20Settlement.png)


4) **Train the Model:**
   - In the terminal, run:
     ```
     rasa train
     ```

6. **Talk to your Bot:**
   - In the terminal, run
     ```
     rasa inspect or rasa shell
     ```
     GitHub will show a notification, click on the green button to view the inspector where you can chat with your assistant.

7. **Run Custom Actions:**
  In Rasa 3.10 and later, custom actions are automatically run as part of your running assistant. To double-check that this is set up correctly, ensure that your `endpoints.yml` file contains the following configuration:
   ```
   action_endpoint:
      actions_module: "actions" # path to your actions package
    ```
   Then re-run your assistant via `rasa inspect` every time you make changes to your custom actions.
