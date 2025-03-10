import json
import os
import re
import logging
import markdown
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE")

logging_config = {
    "level": getattr(logging, log_level),
    "format": "%(asctime)s - %(levelname)s - %(message)s"
}

if log_file:
    logging_config["filename"] = log_file
    logging_config["filemode"] = "a"

logging.basicConfig(**logging_config)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ContextManager:
    def __init__(self, summary_dir="summary"):
        self.summary_dir = Path(summary_dir)
        self.file_summaries = self._load_file_summaries()
        self.module_summaries = self._load_module_summaries()
        self.app_overview = self._load_app_overview()
        self.api_flows = self._load_api_flows()
        self.component_matrix = self._load_component_matrix()
        self.prompt_templates = self._load_prompt_templates()
        
        # Initialize the sentence transformer model
        logger.info("Loading sentence transformer model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self._create_embeddings()
        logger.info("Context manager initialized successfully")

    def _load_file_summaries(self):
        """Load all file summaries from the file_summaries directory."""
        summaries = {}
        file_summaries_dir = self.summary_dir / "file_summaries"
        
        if not file_summaries_dir.exists():
            logger.warning(f"File summaries directory not found: {file_summaries_dir}")
            return summaries
            
        for file_path in file_summaries_dir.glob("*.md"):
            if "_flow.md" in file_path.name or "_spring.md" in file_path.name:
                continue  # Skip flow and spring analysis files
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract the component name from the file name
            component_name = file_path.stem.split('_')[-1]
            if component_name.endswith('.java'):
                component_name = component_name[:-5]  # Remove .java extension
                
            summaries[component_name] = {
                "file_path": str(file_path),
                "summary": content,
                "type": self._determine_component_type(component_name, content)
            }
            
        logger.info(f"Loaded {len(summaries)} file summaries")
        return summaries
        
    def _determine_component_type(self, component_name, content):
        """Determine the type of component based on its name and content."""
        if "Controller" in component_name:
            return "controller"
        elif "Service" in component_name:
            return "service"
        elif "Repository" in component_name:
            return "repository"
        elif "Entity" in component_name or "Model" in component_name:
            return "model"
        elif "DTO" in component_name or "Input" in component_name:
            return "dto"
        elif "Util" in component_name or "Helper" in component_name:
            return "utility"
        else:
            # Try to determine from content
            if "@Controller" in content or "@RestController" in content:
                return "controller"
            elif "@Service" in content:
                return "service"
            elif "@Repository" in content:
                return "repository"
            elif "@Entity" in content:
                return "model"
            else:
                return "other"

    def _load_module_summaries(self):
        """Load all module summaries from the module_summaries directory."""
        summaries = {}
        module_summaries_dir = self.summary_dir / "module_summaries"
        
        if not module_summaries_dir.exists():
            logger.warning(f"Module summaries directory not found: {module_summaries_dir}")
            return summaries
            
        for file_path in module_summaries_dir.glob("*.md"):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract the module name from the file name
            module_name = file_path.stem
            
            summaries[module_name] = {
                "file_path": str(file_path),
                "summary": content
            }
            
        logger.info(f"Loaded {len(summaries)} module summaries")
        return summaries

    def _load_app_overview(self):
        """Load the application overview from the summary_of_summaries.md file."""
        overview_file = self.summary_dir / "summary_of_summaries.md"
        
        if not overview_file.exists():
            logger.warning(f"Application overview file not found: {overview_file}")
            return {"summary": "Application overview not available."}
            
        with open(overview_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return {
            "file_path": str(overview_file),
            "summary": content
        }

    def _load_api_flows(self):
        """Load the enhanced API flow representation."""
        api_flow_file = self.summary_dir / "enhanced_api_flow.json"
        
        if not api_flow_file.exists():
            logger.warning(f"Enhanced API flow file not found: {api_flow_file}")
            return {}
            
        with open(api_flow_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_component_matrix(self):
        """Load the component relationship matrix."""
        matrix_file = self.summary_dir / "component_relationship_matrix.md"
        
        if not matrix_file.exists():
            logger.warning(f"Component relationship matrix file not found: {matrix_file}")
            return {}
            
        with open(matrix_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse the markdown table into a structured format
        matrix = {}
        lines = content.split('\n')
        
        # Skip the header lines (first 3 lines)
        for line in lines[3:]:
            if '|' not in line:
                continue
                
            parts = line.split('|')
            if len(parts) < 4:
                continue
                
            component = parts[1].strip()
            depends_on = [dep.strip() for dep in parts[2].strip().split(', ') if dep.strip()]
            used_by = [user.strip() for user in parts[3].strip().split(', ') if user.strip()]
            
            matrix[component] = {
                "depends_on": depends_on,
                "used_by": used_by
            }
            
        logger.info(f"Loaded component relationship matrix with {len(matrix)} components")
        return matrix

    def _load_prompt_templates(self):
        """Load the LLM prompt templates."""
        templates = {}
        llm_prompts_dir = self.summary_dir / "llm_prompts"
        
        if not llm_prompts_dir.exists():
            logger.warning(f"LLM prompts directory not found: {llm_prompts_dir}")
            return templates
            
        for file_path in llm_prompts_dir.glob("*.md"):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            template_name = file_path.stem
            templates[template_name] = content
            
        logger.info(f"Loaded {len(templates)} prompt templates")
        return templates

    def _create_embeddings(self):
        """Create embeddings for all summaries for similarity search."""
        logger.info("Creating embeddings for summaries...")
        
        # Create embeddings for file summaries
        self.file_summary_embeddings = {}
        for component, data in self.file_summaries.items():
            self.file_summary_embeddings[component] = self.model.encode(data["summary"])
            
        # Create embeddings for module summaries
        self.module_summary_embeddings = {}
        for module, data in self.module_summaries.items():
            self.module_summary_embeddings[module] = self.model.encode(data["summary"])
            
        logger.info("Embeddings created successfully")

    def get_relevant_components(self, query, top_n=5):
        """Get the most relevant components for a query using semantic similarity."""
        query_embedding = self.model.encode(query)
        
        # Calculate similarity with file summaries
        file_similarities = {}
        for component, embedding in self.file_summary_embeddings.items():
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            file_similarities[component] = similarity
            
        # Sort by similarity and get top N
        sorted_components = sorted(file_similarities.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        # Return the relevant components with their summaries
        return {
            component: {
                "summary": self.file_summaries[component]["summary"],
                "type": self.file_summaries[component]["type"],
                "similarity": similarity
            }
            for component, similarity in sorted_components
        }

    def get_related_api_flows(self, components):
        """Get API flows related to the given components."""
        component_names = set(components.keys())
        related_flows = {}
        
        for endpoint_key, flow_data in self.api_flows.items():
            # Check if any component is in the controller, service chain, or repository access
            controller_file = flow_data.get("controller", {}).get("file", "")
            controller_name = controller_file.replace(".java", "")
            
            service_files = [service.get("file", "") for service in flow_data.get("serviceChain", [])]
            service_names = [file.replace(".java", "") for file in service_files]
            
            repo_files = [repo.get("file", "") for repo in flow_data.get("repositoryAccess", [])]
            repo_names = [file.replace(".java", "") for file in repo_files]
            
            # Check if any component is related to this flow
            if (controller_name in component_names or 
                any(name in component_names for name in service_names) or
                any(name in component_names for name in repo_names)):
                related_flows[endpoint_key] = flow_data
                
        return related_flows

    def get_related_matrix_entries(self, components):
        """Get component relationship matrix entries related to the given components."""
        component_names = set(components.keys())
        related_entries = {}
        
        for component, relationships in self.component_matrix.items():
            # Include if the component is in our list or if it depends on or is used by any of our components
            depends_on = set(relationships.get("depends_on", []))
            used_by = set(relationships.get("used_by", []))
            
            if (component in component_names or 
                depends_on.intersection(component_names) or 
                used_by.intersection(component_names)):
                related_entries[component] = relationships
                
        return related_entries

    def get_prompt_template(self, template_name):
        """Get a prompt template by name."""
        return self.prompt_templates.get(template_name, "")


class LLMClient:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found in environment variables")
            
        self.client = OpenAI(api_key=api_key)
        
        # Get configuration from environment variables
        self.default_model = os.getenv("LLM_MODEL", "gpt-4-turbo")
        self.default_temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.default_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
        
        logger.info(f"LLM client initialized with model: {self.default_model}")

    def analyze_application(self, prompt, model=None, temperature=None, max_tokens=None):
        """Send a prompt to the LLM and get a response."""
        try:
            # Use environment variables as defaults if not specified
            model = model or self.default_model
            temperature = temperature if temperature is not None else self.default_temperature
            max_tokens = max_tokens or self.default_max_tokens
            
            logger.info(f"Sending prompt to LLM (length: {len(prompt)} chars, model: {model})")
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            return f"Error: {str(e)}"


class QueryProcessor:
    def __init__(self, summary_dir="summary"):
        self.context_manager = ContextManager(summary_dir)
        self.llm_client = LLMClient()
        logger.info("Query processor initialized")

    def build_prompt(self, query, context, template_name="general_analysis_template"):
        """Build a prompt using a template and context."""
        template = self.context_manager.get_prompt_template(template_name)
        
        if not template:
            logger.warning(f"Template '{template_name}' not found, using default format")
            template = """# Spring Boot Application Analysis

## Application Context
{app_overview}

## Components Relevant to Query
{components}

## API Flows Related to Query
{api_flows}

## Component Relationships
{matrix}

## Question
{query}

## Instructions
1. Analyze the question in relation to the provided Spring Boot application context
2. Provide a detailed technical response addressing the question
3. Cite specific code files and components in your answer using the format [FileName.java]
4. Identify any potential impacts or considerations across components
5. If any information seems missing, note assumptions you're making
"""
        
        # Format the components section
        components_text = ""
        for component, data in context["components"].items():
            components_text += f"### {component}\n{data['summary']}\n\n"
            
        # Format the API flows section
        api_flows_text = json.dumps(context["api_flows"], indent=2)
        
        # Format the matrix section
        matrix_text = ""
        for component, relationships in context["matrix"].items():
            depends_on = ", ".join(relationships["depends_on"]) if relationships["depends_on"] else "None"
            used_by = ", ".join(relationships["used_by"]) if relationships["used_by"] else "None"
            matrix_text += f"- {component}:\n  - Depends on: {depends_on}\n  - Used by: {used_by}\n\n"
        
        # Replace placeholders in the template
        prompt = template.replace("{insert relevant high-level application summary}", context["app_overview"]["summary"])
        prompt = prompt.replace("{insert summaries of the 3-5 most relevant components}", components_text)
        prompt = prompt.replace("{insert API flow data for endpoints relevant to the query}", api_flows_text)
        prompt = prompt.replace("{insert specific question}", query)
        
        # For templates that don't use the exact placeholders
        prompt = prompt.replace("{app_overview}", context["app_overview"]["summary"])
        prompt = prompt.replace("{components}", components_text)
        prompt = prompt.replace("{api_flows}", api_flows_text)
        prompt = prompt.replace("{matrix}", matrix_text)
        prompt = prompt.replace("{query}", query)
        
        return prompt

    def process_query(self, query, template_name="general_analysis_template", verify=True):
        """Process a query about the Spring Boot application."""
        logger.info(f"Processing query: {query}")
        
        # Step 1: Retrieve relevant context
        relevant_components = self.context_manager.get_relevant_components(query)
        
        # Step 2: Build context payload
        context = {
            "app_overview": self.context_manager.app_overview,
            "components": relevant_components,
            "api_flows": self.context_manager.get_related_api_flows(relevant_components),
            "matrix": self.context_manager.get_related_matrix_entries(relevant_components)
        }
        
        # Step 3: Build and execute prompt
        prompt = self.build_prompt(query, context, template_name)
        response = self.llm_client.analyze_application(prompt)
        
        # Step 4: Self-correction if requested
        if verify:
            logger.info("Performing self-verification of response")
            verified_response = self._verify_response(response, context)
            return verified_response
        
        return response

    def _verify_response(self, response, context):
        """Verify the response against the context for accuracy."""
        # Build a verification prompt
        verification_template = self.context_manager.get_prompt_template("self_correction_template")
        
        if not verification_template:
            logger.warning("Self-correction template not found, using default format")
            verification_template = """# Self-Correction Review

## Original Response
{response}

## Application Context
{app_overview}

## Component Relationships
{matrix}

## Instructions
Review the original response and verify:
1. Are all cited files actually mentioned in the application context?
2. Are the described relationships between components consistent with the provided component relationship matrix?
3. Are the described API flows consistent with the provided API flow data?
4. Does the impact analysis consider all dependent components from the relationship matrix?
5. Correct any inconsistencies and explain the corrections.
"""
        
        # Format the matrix section
        matrix_text = ""
        for component, relationships in context["matrix"].items():
            depends_on = ", ".join(relationships["depends_on"]) if relationships["depends_on"] else "None"
            used_by = ", ".join(relationships["used_by"]) if relationships["used_by"] else "None"
            matrix_text += f"- {component}:\n  - Depends on: {depends_on}\n  - Used by: {used_by}\n\n"
        
        # Replace placeholders in the template
        verification_prompt = verification_template.replace("{insert original LLM response}", response)
        verification_prompt = verification_template.replace("{insert relevant high-level application summary}", context["app_overview"]["summary"])
        verification_prompt = verification_template.replace("{insert relevant portion of component relationship matrix}", matrix_text)
        
        # For templates that don't use the exact placeholders
        verification_prompt = verification_prompt.replace("{response}", response)
        verification_prompt = verification_prompt.replace("{app_overview}", context["app_overview"]["summary"])
        verification_prompt = verification_prompt.replace("{matrix}", matrix_text)
        
        # Send the verification prompt to the LLM
        verified_response = self.llm_client.analyze_application(verification_prompt)
        return verified_response

    def analyze_feature_implementation(self, feature_description):
        """Analyze how a new feature would be implemented in the application."""
        return self.process_query(feature_description, template_name="feature_implementation_template")

    def analyze_code_change_impact(self, change_description):
        """Analyze the impact of a code change on the application."""
        return self.process_query(change_description, template_name="code_change_impact_template")


# Example usage
if __name__ == "__main__":
    processor = QueryProcessor()
    
    # Example queries
    queries = [
        "What is the overall architecture of this Spring Boot application?",
        "How does the transaction flow work in this application?",
        "What would be the impact of adding a new 'address' field to the User entity?",
        "How would I implement JWT authentication in this application?"
    ]
    
    # Process each query
    for query in queries:
        print(f"\n\n{'='*80}\nQUERY: {query}\n{'='*80}\n")
        response = processor.process_query(query)
        print(f"\nRESPONSE:\n{response}")
        
    # Example feature implementation analysis
    feature = "Add a feature to allow users to set up recurring transfers between accounts"
    print(f"\n\n{'='*80}\nFEATURE IMPLEMENTATION: {feature}\n{'='*80}\n")
    response = processor.analyze_feature_implementation(feature)
    print(f"\nANALYSIS:\n{response}")
    
    # Example code change impact analysis
    change = "Change the Transaction entity to include a 'category' field for transaction categorization"
    print(f"\n\n{'='*80}\nCODE CHANGE IMPACT: {change}\n{'='*80}\n")
    response = processor.analyze_code_change_impact(change)
    print(f"\nIMPACT ANALYSIS:\n{response}") 