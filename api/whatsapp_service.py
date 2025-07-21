import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
import json
from enum import Enum
import time
from functools import wraps
import hashlib
import uuid

# Enhanced imports for better performance and capabilities
from sentence_transformers import SentenceTransformer, CrossEncoder
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from pinecone import Pinecone
import openai
import dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import tiktoken
from uwsbot.api.db import ConversationManager  # <-- Add this import

# Load environment variables
dotenv.load_dotenv()
os.environ["OTEL_TRACES_EXPORTER"] = "none"

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('uws_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Enhanced query classification"""
    ADMISSIONS = "admissions"
    COURSES = "courses" 
    FEES_FUNDING = "fees_funding"
    CAMPUS_FACILITIES = "campus_facilities"
    VISA_IMMIGRATION = "visa_immigration"
    STUDENT_SUPPORT = "student_support"
    ACADEMIC_CALENDAR = "academic_calendar"
    ACCOMMODATION = "accommodation"
    CAREERS = "careers"
    GENERAL_INFO = "general_info"
    PERSONAL_CHAT = "personal_chat"
    GREETING = "greeting"
    COMPLAINT = "complaint"
    URGENT = "urgent"

class ConfidenceLevel(Enum):
    """Search confidence levels"""
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"
    NONE = "none"

@dataclass
class SearchResult:
    content: str
    score: float
    metadata: Dict[str, Any]
    rerank_score: Optional[float] = None
    source: Optional[str] = None
    relevance_explanation: Optional[str] = None

@dataclass
class UserContext:
    """Enhanced user context tracking"""
    user_id: str
    name: Optional[str] = None
    preferred_language: str = "en"
    conversation_history: List[Dict] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    last_query_type: Optional[QueryType] = None
    session_start: datetime = field(default_factory=datetime.now)
    urgency_level: int = 0  # 0-5 scale
    student_status: Optional[str] = None  # prospective, current, alumni
    study_level: Optional[str] = None  # undergraduate, postgraduate
    is_international: Optional[bool] = None

@dataclass
class CRAGResult:
    results: List[SearchResult]
    confidence_level: ConfidenceLevel
    search_strategy_used: str
    query_rewritten: bool
    original_query: str
    final_query: str
    search_time: float
    tokens_used: int = 0
    fallback_triggered: bool = False

def performance_monitor(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"⚡ {func.__name__} executed in {execution_time:.2f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ {func.__name__} failed after {execution_time:.2f}s: {e}")
            raise
    return wrapper

def cache_result(ttl_seconds: int = 300):
    """Simple caching decorator for frequently accessed data"""
    cache = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = hashlib.md5(f"{func.__name__}_{str(args)}_{str(kwargs)}".encode()).hexdigest()
            
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < ttl_seconds:
                    logger.debug(f"📦 Cache hit for {func.__name__}")
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, time.time())
            logger.debug(f"💾 Cached result for {func.__name__}")
            return result
        return wrapper
    return decorator

class EnhancedQueryAnalyzer:
    """Advanced query analysis with ML-based intent detection"""
    
    def __init__(self):
        self.intent_patterns = {
            QueryType.ADMISSIONS: [
                r'\b(apply|application|admission|entry|requirement|deadline|qualify)\b',
                r'\b(how to apply|when to apply|application process)\b',
                r'\b(UCAS|conditional offer|unconditional)\b'
            ],
            QueryType.COURSES: [
                r'\b(course|program|degree|study|subject|module|curriculum|major)\b',
                r'\b(computer science|engineering|business|psychology|nursing)\b',
                r'\b(undergraduate|postgraduate|masters|PhD|bachelor)\b'
            ],
            QueryType.FEES_FUNDING: [
                r'\b(fee|cost|tuition|price|payment|scholarship|funding|bursary)\b',
                r'\b(how much|expensive|afford|student loan)\b',
                r'\b(international fees|home fees|EU fees)\b'
            ],
            QueryType.VISA_IMMIGRATION: [
                r'\b(visa|immigration|tier 4|student visa|CAS|sponsorship|interview)\b',
                r'\b(international student|work permit|stay after study)\b',
                r'\b(credibility interview|pre-cas|confirmation of acceptance)\b'
            ],
            QueryType.ACCOMMODATION: [
                r'\b(accommodation|housing|residence|dormitory|flat|room)\b',
                r'\b(where to live|student accommodation|halls)\b'
            ],
            QueryType.CAMPUS_FACILITIES: [
                r'\b(campus|library|gym|facilities|sports|dining|cafeteria)\b',
                r'\b(student union|societies|clubs|activities)\b'
            ],
            QueryType.STUDENT_SUPPORT: [
                r'\b(support|help|counseling|guidance|wellbeing|mental health)\b',
                r'\b(academic support|study skills|disability support)\b'
            ],
            QueryType.CAREERS: [
                r'\b(career|job|employment|placement|internship|graduate)\b',
                r'\b(career service|job fair|work experience)\b'
            ],
            QueryType.URGENT: [
                r'\b(urgent|emergency|asap|immediate|deadline|quick)\b',
                r'\b(need help now|very important|time sensitive)\b'
            ],
            QueryType.COMPLAINT: [
                r'\b(complain|problem|issue|disappointed|unhappy|wrong)\b',
                r'\b(not working|doesn\'t work|frustrated)\b'
            ],
            QueryType.GREETING: [
                r'\b(hello|hi|hey|good morning|good afternoon|good evening)\b',
                r'^(hi|hello|hey)$'
            ]
        }
        
        # Entity extraction patterns
        self.entity_patterns = {
            'course_names': r'\b(computer science|engineering|business|psychology|nursing|medicine|law)\b',
            'study_levels': r'\b(undergraduate|postgraduate|masters|phd|bachelor)\b',
            'locations': r'\b(paisley|hamilton|dumfries|london|ayr)\b',
            'deadlines': r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\w+ \d{1,2}|\d{1,2} \w+)\b'
        }
    
    def analyze_query(self, query: str, user_context: UserContext) -> Dict[str, Any]:
        """Enhanced query analysis with context awareness"""
        query_lower = query.lower().strip()
        
        # Detect query type using pattern matching
        detected_types = []
        for query_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    detected_types.append(query_type)
                    break
        
        # Primary query type (most specific wins)
        primary_type = detected_types[0] if detected_types else QueryType.GENERAL_INFO
        
        # Extract entities
        entities = {}
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            if matches:
                entities[entity_type] = list(set(matches))
        
        # Assess urgency
        urgency_indicators = ['urgent', 'asap', 'immediate', 'quickly', 'deadline', 'emergency']
        urgency_score = sum(1 for word in urgency_indicators if word in query_lower)
        
        # Detect question type
        question_words = ['what', 'how', 'when', 'where', 'why', 'which', 'who', 'can', 'should', 'will']
        is_question = any(word in query_lower for word in question_words) or query.endswith('?')
        
        # Context-aware analysis
        context_boost = 0
        if user_context.last_query_type and primary_type == user_context.last_query_type:
            context_boost = 0.2  # User likely continuing same topic
        
        return {
            'primary_type': primary_type,
            'all_types': detected_types,
            'entities': entities,
            'is_question': is_question,
            'urgency_score': urgency_score,
            'complexity': self._assess_complexity(query),
            'context_boost': context_boost,
            'requires_personalization': self._needs_personalization(query, entities),
            'word_count': len(query.split()),
            'has_specific_requirements': bool(entities)
        }
    
    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity for search strategy"""
        word_count = len(query.split())
        if word_count > 15 or 'and' in query.lower() or 'also' in query.lower():
            return 'high'
        elif word_count > 8:
            return 'medium'
        return 'simple'
    
    def _needs_personalization(self, query: str, entities: Dict) -> bool:
        """Check if query needs personalized response"""
        personal_indicators = ['my', 'i', 'me', 'for me', 'should i', 'can i']
        return any(indicator in query.lower() for indicator in personal_indicators)

class OptimizedPineconeSearchEngine:
    """Production-ready search engine with advanced CRAG capabilities"""
    
    def __init__(self, api_key: str, index_name: str = "uws-knowledge"):
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)
        
        # Load models with error handling
        try:
            # Initialize reranker only - using OpenAI for embeddings
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("✅ ML models loaded successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load reranker model: {e}. Continuing without reranking.")
            self.reranker = None
        
        # OpenAI client with retry logic
        self.openai_client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=30.0,
            max_retries=3
        )
        
        # Enhanced UWS knowledge patterns
        self.uws_knowledge_map = {
            QueryType.ADMISSIONS: {
                'keywords': ['apply', 'application', 'admission', 'entry', 'requirement', 'UCAS', 'deadline'],
                'boost_terms': ['UWS application', 'admission requirements', 'entry criteria']
            },
            QueryType.COURSES: {
                'keywords': ['course', 'program', 'degree', 'study', 'curriculum', 'module'],
                'boost_terms': ['UWS courses', 'degree programs', 'course content']
            },
            QueryType.FEES_FUNDING: {
                'keywords': ['fee', 'cost', 'tuition', 'funding', 'scholarship', 'bursary'],
                'boost_terms': ['UWS fees', 'tuition costs', 'financial support']
            },
            QueryType.VISA_IMMIGRATION: {
                'keywords': ['visa', 'immigration', 'international', 'CAS', 'sponsorship', 'interview', 'credibility'],
                'boost_terms': ['student visa', 'international students', 'UK visa requirements', 'CAS interview']
            }
        }
        
        # Token counting for cost optimization
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Performance metrics
        self.search_metrics = {
            'total_searches': 0,
            'cache_hits': 0,
            'average_response_time': 0,
            'tokens_consumed': 0
        }
        
        # Query analyzer
        self.query_analyzer = EnhancedQueryAnalyzer()
    
    @performance_monitor
    @cache_result(ttl_seconds=300)
    def get_embeddings(self, text: str) -> List[float]:
        """Optimized embedding generation with caching (OpenAI, 512d)"""
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            full_embedding = response.data[0].embedding
            return full_embedding[:512]
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            return []
    
    @performance_monitor
    def generate_enhanced_queries(self, query: str, query_analysis: Dict, user_context: UserContext) -> List[str]:
        """Generate optimized search queries using GPT-4 with context awareness"""
        try:
            # Build context-aware prompt
            context_info = ""
            if user_context.student_status:
                context_info += f"User is a {user_context.student_status} student. "
            if user_context.study_level:
                context_info += f"Interested in {user_context.study_level} studies. "
            if user_context.is_international:
                context_info += "International student perspective needed. "
            
            # Get knowledge mapping for query type
            query_type = query_analysis['primary_type']
            knowledge_context = self.uws_knowledge_map.get(query_type, {})
            
            system_prompt = f"""You are an expert search query optimizer for University of the West of Scotland (UWS).

CONTEXT: {context_info}
QUERY TYPE: {query_type.value}
ENTITIES FOUND: {query_analysis.get('entities', {})}
URGENCY: {query_analysis.get('urgency_score', 0)}

Generate 3 optimized search queries that will find the most relevant UWS information.

OPTIMIZATION RULES:
1. Make queries more specific and keyword-rich
2. Include relevant university terminology: {', '.join(knowledge_context.get('keywords', []))}
3. Add context words like "UWS", "University of the West of Scotland" where appropriate
4. For international students, include "international" context
5. For urgent queries, prioritize deadlines and requirements
6. Break complex questions into focused searches

Original query: "{query}"

Return ONLY a JSON array of 3 strings, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.2,
                max_tokens=150,
                timeout=15
            )
            
            # Count tokens for metrics
            tokens_used = len(self.tokenizer.encode(system_prompt + query))
            self.search_metrics['tokens_consumed'] += tokens_used
            
            result = response.choices[0].message.content.strip()
            
            try:
                enhanced_queries = json.loads(result)
                if isinstance(enhanced_queries, list) and len(enhanced_queries) >= 2:
                    return enhanced_queries[:3]
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Failed to parse LLM response: {result}")
            
        except Exception as e:
            logger.error(f"❌ Query enhancement failed: {e}")
        
        # Fallback query generation
        fallback_queries = [query]
        
        # Add UWS context
        if "UWS" not in query and "university" not in query.lower():
            fallback_queries.append(f"UWS {query}")
        
        # Add query type specific terms
        if query_type in self.uws_knowledge_map:
            boost_terms = self.uws_knowledge_map[query_type]['boost_terms']
            if boost_terms:
                fallback_queries.append(f"{query} {boost_terms[0]}")
        
        return fallback_queries[:3]
    
    @performance_monitor
    def multi_strategy_search(self, queries: List[str], top_k: int = 12) -> List[SearchResult]:
        """Parallel multi-query search with deduplication"""
        all_results = {}
        
        def search_single_query(query: str) -> List[SearchResult]:
            try:
                query_embedding = self.get_embeddings(query)
                if not query_embedding:
                    return []
                
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k // len(queries) + 3,
                    include_metadata=True,
                    include_values=False,
                    namespace='website-2025'  # Restrict search to the 'website-2025' namespace
                )
                # Print raw Pinecone results
                # print(f"[PINECONE RAW] Query: '{query}' Results: {results}")
                
                search_results = []
                for match in results.matches:
                    # --- OLD LOGIC (commented out): Only used content field ---
                    # content = (
                    #     match.metadata.get('content', '') or 
                    #     match.metadata.get('chunk_content', '') or 
                    #     match.metadata.get('text', '') or
                    #     str(match.metadata)
                    # ).strip()
                    # if content and len(content) > 50:
                    #     search_results.append(SearchResult(
                    #         content=content,
                    #         score=match.score,
                    #         metadata=match.metadata,
                    #         source=match.metadata.get('source', 'unknown')
                    #     ))
                    # --- NEW LOGIC: Use full object ---
                    full_object = match.metadata
                    # You can optionally filter on answer length, or just always include
                    answer = full_object.get('answer', '')
                    if answer and len(answer) > 2:  # You can adjust this threshold
                        search_results.append(SearchResult(
                            content=answer,  # For backward compatibility, but you can use full_object elsewhere
                            score=match.score,
                            metadata=full_object,
                            source=full_object.get('source', 'unknown')
                        ))
                # print(f"[PINECONE PROCESSED] Query: '{query}' Results: {[{'score': r.score, 'content': r.content[:100]} for r in search_results]}")
                return search_results
            except Exception as e:
                logger.error(f"❌ Search failed for query '{query}': {e}")
                return []
        
        # Parallel search execution
        with ThreadPoolExecutor(max_workers=min(len(queries), 3)) as executor:
            future_to_query = {executor.submit(search_single_query, query): query for query in queries}
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results = future.result(timeout=10)
                    for result in results:
                        # Use content hash for deduplication
                        content_hash = hashlib.md5(result.content.encode()).hexdigest()
                        if content_hash not in all_results or result.score > all_results[content_hash].score:
                            all_results[content_hash] = result
                except Exception as e:
                    logger.error(f"❌ Search timeout/error for query '{query}': {e}")
        
        # Return sorted by score
        final_results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        return final_results[:top_k]
    
    @performance_monitor
    def advanced_reranking(self, query: str, results: List[SearchResult], user_context: UserContext) -> List[SearchResult]:
        """Enhanced reranking with user context"""
        if not results or not self.reranker:
            # If no reranker, just add pseudo rerank scores based on original scores
            for result in results:
                result.rerank_score = result.score
            return results
        
        try:
            # Prepare pairs for reranking
            pairs = []
            context_query = query
            
            # Add user context to query for better reranking
            if user_context.is_international:
                context_query += " international student"
            if user_context.study_level:
                context_query += f" {user_context.study_level}"
            
            for result in results:
                pairs.append((context_query, result.content[:500]))  # Limit content length
            
            # Get reranking scores
            rerank_scores = self.reranker.predict(pairs)
            
            # Apply scores and additional context boost
            for i, result in enumerate(results):
                result.rerank_score = float(rerank_scores[i])
                
                # Boost scores based on user context
                if user_context.is_international and 'international' in result.content.lower():
                    result.rerank_score += 0.5
                
                if user_context.study_level and user_context.study_level in result.content.lower():
                    result.rerank_score += 0.3
            
            # Sort by rerank score
            reranked = sorted(results, key=lambda x: x.rerank_score, reverse=True)
            
            logger.info(f"🔄 Reranked {len(results)} results. Top score: {reranked[0].rerank_score:.3f}")
            return reranked
            
        except Exception as e:
            logger.error(f"❌ Reranking failed: {e}")
            # Fallback: use original scores as rerank scores
            for result in results:
                result.rerank_score = result.score
            return results
    
    @performance_monitor
    def assess_result_quality(self, query: str, results: List[SearchResult], query_analysis: Dict) -> ConfidenceLevel:
        """FIXED: More accurate quality assessment"""
        if not results:
            return ConfidenceLevel.NONE
        
        # Score-based assessment - FIXED: Use proper score ranges for Pinecone
        top_score = results[0].rerank_score or results[0].score
        
        # FIXED: Pinecone cosine similarity scores are between 0-1, not 0-5
        # Adjust thresholds accordingly
        score_threshold_high = 0.7   # High confidence for cosine similarity
        score_threshold_medium = 0.5  # Medium confidence
        score_threshold_low = 0.3     # Low confidence
        
        # Content relevance check
        query_terms = set(query.lower().split())
        content_matches = 0
        
        for result in results[:3]:
            result_terms = set(result.content.lower().split())
            overlap = len(query_terms.intersection(result_terms))
            if overlap >= len(query_terms) * 0.3:  # 30% term overlap
                content_matches += 1
        
        # Entity-based boost
        entities_found = any(
            entity in results[0].content.lower() 
            for entity_list in query_analysis.get('entities', {}).values() 
            for entity in entity_list
        )
        
        # Keyword relevance check - FIXED: Check for query-specific keywords
        query_lower = query.lower()
        relevant_keywords_found = 0
        top_content = results[0].content.lower()
        
        # Check for specific keyword matches
        if 'cas' in query_lower and 'cas' in top_content:
            relevant_keywords_found += 1
        if 'interview' in query_lower and 'interview' in top_content:
            relevant_keywords_found += 1
        if 'visa' in query_lower and 'visa' in top_content:
            relevant_keywords_found += 1
        if 'process' in query_lower and 'process' in top_content:
            relevant_keywords_found += 1
        
        # FIXED: More lenient confidence assessment
        logger.info(f"🔍 Quality Assessment - Score: {top_score:.3f}, Content matches: {content_matches}, Keywords: {relevant_keywords_found}, Entities: {entities_found}")
        
        # Determine confidence level with more realistic thresholds
        if top_score >= score_threshold_high and (content_matches >= 2 or relevant_keywords_found >= 2):
            return ConfidenceLevel.HIGH
        elif top_score >= score_threshold_medium and (content_matches >= 1 or relevant_keywords_found >= 1 or entities_found):
            return ConfidenceLevel.MEDIUM
        elif top_score >= score_threshold_low or content_matches >= 1 or relevant_keywords_found >= 1:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NONE
    
    @performance_monitor
    def crag_search(self, query: str, user_context: UserContext, top_k: int = 10) -> CRAGResult:
        """Production-ready Corrective RAG implementation"""
        start_time = time.time()
        self.search_metrics['total_searches'] += 1
        
        # Step 1: Analyze query with context
        query_analysis = self.query_analyzer.analyze_query(query, user_context)
        logger.info(f"🔍 Query analysis: {query_analysis['primary_type'].value}, urgency: {query_analysis['urgency_score']}")
        
        # Step 2: Generate enhanced queries
        enhanced_queries = self.generate_enhanced_queries(query, query_analysis, user_context)
        query_rewritten = enhanced_queries[0] != query
        
        # Step 3: Multi-strategy parallel search
        search_results = self.multi_strategy_search(enhanced_queries, top_k * 2)
        
        if not search_results:
            return CRAGResult(
                results=[],
                confidence_level=ConfidenceLevel.NONE,
                search_strategy_used="multi_query_parallel",
                query_rewritten=query_rewritten,
                original_query=query,
                final_query=enhanced_queries[0],
                search_time=time.time() - start_time,
                fallback_triggered=True
            )
        
        # Step 4: Advanced reranking with context
        reranked_results = self.advanced_reranking(query, search_results, user_context)
        
        # Step 5: Quality assessment
        confidence = self.assess_result_quality(query, reranked_results, query_analysis)
        
        # Step 6: Apply corrective filtering
        final_results = self._apply_corrective_filtering(reranked_results, confidence, top_k)
        
        search_time = time.time() - start_time
        self.search_metrics['average_response_time'] = (
            self.search_metrics['average_response_time'] * (self.search_metrics['total_searches'] - 1) + search_time
        ) / self.search_metrics['total_searches']
        
        return CRAGResult(
            results=final_results,
            confidence_level=confidence,
            search_strategy_used="crag_parallel_rerank_context",
            query_rewritten=query_rewritten,
            original_query=query,
            final_query=enhanced_queries[0],
            search_time=search_time,
            fallback_triggered=confidence == ConfidenceLevel.NONE
        )
    
    def _apply_corrective_filtering(self, results: List[SearchResult], confidence: ConfidenceLevel, top_k: int) -> List[SearchResult]:
        """FIXED: More lenient filtering to preserve good results"""
        if confidence == ConfidenceLevel.HIGH:
            # Keep more results for high confidence
            threshold = 0.3   # Very lenient for high confidence
            max_results = top_k
        elif confidence == ConfidenceLevel.MEDIUM:
            # Moderate filtering
            threshold = 0.25  # Still quite lenient
            max_results = max(3, top_k // 2)
        elif confidence == ConfidenceLevel.LOW:
            # Even low confidence results might be useful
            threshold = 0.2   # Very lenient
            max_results = min(3, max(2, top_k // 3))
        else:
            # NONE confidence - still try to return something useful
            threshold = 0.1   # Extremely lenient
            max_results = min(2, len(results))
        
        # FIXED: Use original score if rerank_score is not available or too low
        filtered = []
        for result in results:
            score_to_use = result.rerank_score if result.rerank_score is not None else result.score
            if score_to_use > threshold:
                filtered.append(result)
        
        # If no results pass threshold, take top results anyway (better than returning nothing)
        if not filtered and results:
            logger.warning(f"⚠️ No results passed threshold {threshold}, returning top {min(2, len(results))} anyway")
            filtered = results[:min(2, len(results))]
            
        return filtered[:max_results]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get search engine performance metrics"""
        return {
            **self.search_metrics,
            'cache_hit_rate': self.search_metrics['cache_hits'] / max(1, self.search_metrics['total_searches'])
        }

class ContextAwareMemoryManager:
    """Enhanced memory management with conversation context"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conversation_buffer = []
        self.max_buffer_size = 10
    
    def extract_conversation_context(self, user_message: str, bot_response: str) -> Dict[str, Any]:
        """Extract meaningful context from conversation"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'bot_response': bot_response,
            'query_type': None,
            'entities_mentioned': [],
            'user_intent': None
        }
        
        # Analyze user message for context
        analyzer = EnhancedQueryAnalyzer()
        analysis = analyzer.analyze_query(user_message, UserContext(user_id=self.user_id))
        
        context['query_type'] = analysis['primary_type'].value
        context['entities_mentioned'] = list(analysis.get('entities', {}).values())
        
        return context
    
    def should_save_to_memory(self, context: Dict[str, Any]) -> bool:
        """Determine if conversation should be saved to long-term memory"""
        # Save if contains important information
        important_indicators = [
            'application', 'course', 'fee', 'deadline', 'visa', 
            'accommodation', 'my name is', 'i am studying', 'i want to study'
        ]
        
        user_msg = context.get('user_message', '').lower()
        return any(indicator in user_msg for indicator in important_indicators)

# Initialize optimized components
try:
    search_engine = OptimizedPineconeSearchEngine(
        api_key=os.getenv("PINECONE_API_KEY"),
        index_name=os.getenv("PINECONE_INDEX_NAME", "uws-knowledge"),
       
    )
    logger.info("✅ Search engine initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize search engine: {e}")
    search_engine = None

@tool
def enhanced_uws_search(query: str, user_id: str = "default") -> str:
    """
    Production-ready UWS knowledge search with advanced CRAG capabilities.
    
    Features:
    - Context-aware query analysis and enhancement
    - Parallel multi-query search for better coverage
    - Advanced reranking with cross-encoder models
    - Smart confidence assessment and filtering
    - Performance monitoring and caching
    - User context integration for personalized results
    
    Returns highly relevant UWS information or 'NO_RELEVANT_INFO' for fallback.
    """
    if not search_engine:
        logger.error("❌ Search engine not available")
        return "NO_RELEVANT_INFO"
    
    try:
        # Create user context (in production, this would be loaded from database)
        user_context = UserContext(user_id=user_id)
        
        # Perform enhanced CRAG search
        crag_result = search_engine.crag_search(query, user_context, top_k=6)
        
        # Comprehensive logging
        logger.info(f"🔍 CRAG Search Summary:")
        logger.info(f"  ├─ User: {user_id}")
        logger.info(f"  ├─ Original: {crag_result.original_query}")
        logger.info(f"  ├─ Enhanced: {crag_result.final_query}")
        logger.info(f"  ├─ Rewritten: {crag_result.query_rewritten}")
        logger.info(f"  ├─ Confidence: {crag_result.confidence_level.value}")
        logger.info(f"  ├─ Results: {len(crag_result.results)}")
        logger.info(f"  ├─ Time: {crag_result.search_time:.2f}s")
        logger.info(f"  └─ Strategy: {crag_result.search_strategy_used}")
        
        # FIXED: More lenient result acceptance - accept results even with NONE confidence if they exist
        if crag_result.results and len(crag_result.results) > 0:
            # Combine top results with quality markers
            combined_results = []
            
            for i, result in enumerate(crag_result.results[:3]):
                content = result.content.strip()
                # FIXED: More lenient content filtering
                if content and len(content) > 50:  # Reduced from 150 to 50
                    # Add relevance context for debugging
                    if logger.isEnabledFor(logging.INFO):
                        score_info = f"Score={result.score:.3f}"
                        if result.rerank_score is not None:
                            score_info += f", Rerank={result.rerank_score:.3f}"
                        logger.info(f"  📄 Result {i+1}: {score_info}")
                    
                    combined_results.append(content)
            
            if combined_results:
                final_response = "\n\n---\n\n".join(combined_results)
                logger.info(f"✅ Returning {len(combined_results)} results (confidence: {crag_result.confidence_level.value})")
                return final_response
        
        # Log fallback reasons with more detail
        logger.warning(f"⚠️ Triggering fallback:")
        logger.warning(f"  ├─ Confidence: {crag_result.confidence_level.value}")
        logger.warning(f"  ├─ Results count: {len(crag_result.results)}")
        logger.warning(f"  ├─ Search time: {crag_result.search_time:.2f}s")
        logger.warning(f"  └─ Query: {query}")
        
        # If we have results but they're not good enough, still log what we found
        if crag_result.results:
            logger.warning(f"  📋 Available results summary:")
            for i, result in enumerate(crag_result.results[:2]):
                logger.warning(f"    {i+1}. Score: {result.score:.3f}, Length: {len(result.content)}")
                
        return "NO_RELEVANT_INFO"
        
    except Exception as e:
        logger.error(f"❌ Enhanced search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return "NO_RELEVANT_INFO"

def create_optimized_uws_agent(user_id: str, all_tools: List, system_message_extra: str = "") -> Agent:
    """Create the most advanced UWS assistant possible"""
    
    return Agent(
        role="Elite UWS Student Success Assistant",
        goal=(
            f"🎯 MISSION: Be the most helpful, intelligent, and human-like UWS assistant for WhatsApp.\n\n"
            
            f"CORE CAPABILITIES:\n"
            f"• 🧠 Advanced AI reasoning with context awareness\n"
            f"• 🔍 Production-grade search with CRAG technology\n"
            f"• 💭 Smart conversation memory and personalization\n"
            f"• ⚡ Real-time performance optimization\n"
            f"• 🎯 Intent-driven responses with emotional intelligence\n"
            f"• 🌍 Multi-cultural student support\n\n"
            
            f"ENHANCED INTELLIGENCE:\n"
            f"• Understand complex, multi-part questions\n"
            f"• Maintain conversation context across interactions\n"
            f"• Provide proactive, anticipatory assistance\n"
            f"• Adapt communication style to user preferences\n"
            f"• Handle edge cases and ambiguous queries gracefully\n"
            f"• Learn from interaction patterns (within session)\n\n"
            
            f"TOOL MASTERY:\n"
            f"1. ENHANCED MEMORY SYSTEM:\n"
            f"   - Always use user_id: {user_id}\n"
            f"   - Check conversation history for seamless continuation\n"
            f"   - Save important user preferences and information\n"
            f"   - Build comprehensive user profile over time\n\n"
            
            f"2. ADVANCED UWS SEARCH:\n"
            f"   - Uses cutting-edge CRAG (Corrective RAG) technology\n"
            f"   - Automatically optimizes queries for better results\n"
            f"   - Provides confidence-scored, highly relevant information\n"
            f"   - Handles complex academic, administrative, and personal queries\n"
            f"   - If search returns 'NO_RELEVANT_INFO', use intelligent fallback\n\n"
            
            f"3. HUBSPOT INTEGRATION:\n"
            f"   - Personalize interactions with user data\n"
            f"   - Facilitate seamless appointment booking\n"
            f"   - Track engagement for improved service\n\n"
            
            f"WHATSAPP OPTIMIZATION:\n"
            f"• Sound completely natural and human-like\n"
            f"• Use appropriate emojis but don't overdo it\n"
            f"• Keep responses conversational and under 1500 characters\n"
            f"• NEVER use robotic phrases like 'It sounds like', 'It appears'\n"
            f"• Anticipate follow-up questions and provide comprehensive answers\n"
            f"• Show empathy and understanding for student concerns\n"
            f"• Be proactive in offering relevant additional information\n\n"
            
            f"INTELLIGENT FALLBACK:\n"
            f"When search returns 'NO_RELEVANT_INFO', provide contextual response:\n"
            f"'I don't have specific details about that in my current knowledge base, but I'm here to help! "
            f"For the most up-to-date information, check https://www.uws.ac.uk or I can connect you with our "
            f"admissions team directly. What other aspects of UWS can I help you explore? 😊'"
        ),
        
        backstory=(
            f"You are UWS's most advanced AI assistant, powered by state-of-the-art technology including "
            f"Corrective RAG for enhanced information retrieval, contextual memory systems, and emotional "
            f"intelligence capabilities. You've been designed to understand not just what students ask, "
            f"but what they really need. You pride yourself on being genuinely helpful, never making up "
            f"information, and always putting student success first. Your advanced search capabilities "
            f"mean you can find relevant information even when students ask questions in unexpected ways. "
            f"You're trusted by thousands of UWS students worldwide and known for your reliability, "
            f"warmth, and ability to make complex university processes feel manageable."
        ),
        
        tools=all_tools,
        verbose=True,
        max_iter=7,
        max_execution_time=90,
        
        system_message=(
            f"🤖 USER CONTEXT: user_id={user_id} (ALWAYS use this exact ID for memory operations)\n\n"
            
            f"⚡ INTELLIGENCE GUIDELINES:\n"
            f"• You have cutting-edge search capabilities - trust the enhanced results\n"
            f"• Always check memory first to understand conversation context\n"
            f"• Be proactive: anticipate needs and offer relevant additional help\n"
            f"• Personalize responses based on user history and preferences\n"
            f"• Handle urgent queries with appropriate priority\n"
            f"• Escalate complex issues to human staff when appropriate\n\n"
            
            f"🎯 RESPONSE OPTIMIZATION:\n"
            f"• NEVER start with robotic phrases - jump straight into helpful content\n"
            f"• For follow-up questions, build on previous context naturally\n"
            f"• Use memory insights to provide more relevant, personalized responses\n"
            f"• Structure complex information clearly with appropriate formatting\n"
            f"• End with relevant follow-up suggestions when helpful\n\n"
            
            f"🚀 PERFORMANCE TARGETS:\n"
            f"• Response time: <30 seconds for complex queries\n"
            f"• Accuracy: >95% for information provided\n"
            f"• User satisfaction: Aim for delighted, not just satisfied\n"
            f"• Context retention: Remember and reference previous interactions\n"
            f"• Proactive assistance: Anticipate and address likely follow-up needs"
        ) + system_message_extra
    )

# Configure MCP servers
def get_mcp_server_params():
    """Get MCP server parameters with flexible paths"""
    return [
        # StdioServerParameters(
        #     command="python3",
        #     args=[os.getenv("HUBSPOT_MCP_PATH", "/path/to/hubspot_server.py")],
        #     env={"HUBSPOT_API_KEY": os.getenv("HUBSPOT_API_KEY")},
        # ),
        # Streamable HTTP MCP server for HubSpot (see https://docs.crewai.com/en/mcp/overview)
        {
            "url": "http://localhost:9003/mcp",
            "transport": "streamable-http"
        },
        StdioServerParameters(
            command=os.getenv("MEM0_PYTHON_PATH", "python3"),
            args=[os.getenv("MEM0_MCP_PATH", "/path/to/mcp_stdio.py")],
            env={
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
                "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
                "POSTGRES_DB": os.getenv("POSTGRES_DB", "stage_genai"),
                "POSTGRES_USER": os.getenv("POSTGRES_USER", "postgres"),
                "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
                "MCP_SESSION_SECRET": os.getenv("MCP_SESSION_SECRET", "your-secure-session-secret"),
                "MCP_RATE_LIMIT": os.getenv("MCP_RATE_LIMIT", "60"),
                "MCP_LOG_LEVEL": os.getenv("MCP_LOG_LEVEL", "INFO")
            },
        ),
    ]

@performance_monitor
def answer_student_query(user_id: str, message: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Main function optimized for FastAPI integration with your exact input format.
    
    Args:
        user_id: User identifier (e.g., "+919449248040")
        message: User message (e.g., "Hello")
    
    Returns:
        Optimized WhatsApp response string
    """
    
    try:
        # Log incoming request
        logger.info(f"📱 Incoming WhatsApp query - User: {user_id}, Message: '{message}'")

        # --- Generate a new Q&A message_id for this user query ---
        qa_message_id = f"msg_{uuid.uuid4()}"

        # Store the user's message in conversation history with the Q&A message_id
        ConversationManager.add_message(
            user_id=user_id,
            sender="user",
            message_text=message,
            metadata={},
            message_id=qa_message_id
        )
        
        # Initialize context manager
        memory_manager = ContextAwareMemoryManager(user_id)
        
        # --- Conversation history integration ---
        # Fetch last 6 messages for context (after storing user message)
        history = ConversationManager.get_conversation_history(user_id, limit=6)
        formatted_history = [
            {"role": ("user" if msg["sender"] == "user" else "assistant"), "content": msg["message_text"]}
            for msg in history
        ]
        # Format as a JSON block for system prompt
        import json as _json
        if formatted_history:
            convo_context = "Conversation history (most recent last):\n" + _json.dumps(formatted_history, indent=2)
        else:
            convo_context = "No previous conversation history."
        # --- End conversation history integration ---
        
        # Get MCP server parameters
        server_params_list = get_mcp_server_params()
        
        with MCPServerAdapter(server_params_list) as mcp_tools:
            # Combine tools
            all_tools = mcp_tools + [enhanced_uws_search]
            
            # --- Inject context into agent ---
            # Pass convo_context into system_message
            agent = create_optimized_uws_agent(
                user_id,
                all_tools,
                system_message_extra=convo_context
            )
            # --- End injection ---
            
            # Create enhanced task
            task = Task(
                description=(
                    f"🎯 WHATSAPP MESSAGE ANALYSIS:\n"
                    f"User ID: {user_id}\n"
                    f"Message: '{message}'\n"
                    f"Timestamp: {datetime.now().isoformat()}\n\n"
                    f"{convo_context}\n\n"  # <-- Add context to task description as well
                    f"🧠 INTELLIGENT RESPONSE STRATEGY:\n\n"
                    
                    f"1. CONTEXT ANALYSIS:\n"
                    f"   ✓ Check user memory for conversation history and preferences\n"
                    f"   ✓ Identify query intent, urgency, and complexity\n"
                    f"   ✓ Determine if this continues a previous conversation\n"
                    f"   ✓ Extract key entities and requirements\n\n"
                    
                    f"2. TOOL SELECTION & EXECUTION:\n"
                    f"   🔍 For UWS information needs:\n"
                    f"      → Use enhanced_uws_search with user_id context\n"
                    f"      → Trust the CRAG results - they're highly optimized\n"
                    f"      → If 'NO_RELEVANT_INFO': use intelligent fallback\n\n"
                    
                    f"   💭 For conversation continuity:\n"
                    f"      → Always check memory first for context\n"
                    f"      → Save important new information shared\n"
                    f"      → Use user_id: {user_id} for all memory operations\n\n"
                    
                    f"   👤 For personalization:\n"
                    f"      → Use HubSpot for user profile information when needed\n"
                    f"      → Adapt response style to user preferences\n"
                    f"      → Reference previous interactions naturally\n\n"
                    
                    f"3. WHATSAPP RESPONSE CRAFTING:\n"
                    f"   ✓ Start directly with helpful content (no 'It sounds like')\n"
                    f"   ✓ Structure information clearly and conversationally\n"
                    f"   ✓ Add relevant emojis naturally (don't overuse)\n"
                    f"   ✓ Stay under 1500 characters for WhatsApp compatibility\n"
                    f"   ✓ End with proactive follow-up suggestions when appropriate\n"
                    f"   ✓ Show empathy and understanding for student concerns\n\n"
                    
                    f"4. QUALITY ASSURANCE:\n"
                    f"   ✓ Ensure accuracy - never hallucinate information\n"
                    f"   ✓ Maintain conversational, human-like tone\n"
                    f"   ✓ Provide value in every response\n"
                    f"   ✓ Be helpful, not just correct\n\n"
                    
                    f"🎯 SUCCESS CRITERIA:\n"
                    f"Deliver a WhatsApp response that feels like talking to the most helpful, "
                    f"knowledgeable friend who happens to be an expert on UWS. The user "
                    f"should feel understood, supported, and confident in the information provided."
                ),
                
                expected_output=(
                    f"A perfectly crafted WhatsApp response that:\n"
                    f"• Addresses the user's specific needs with relevant, accurate information\n"
                    f"• Feels natural and conversational, not robotic or templated\n"
                    f"• Shows understanding of context and previous interactions\n"
                    f"• Provides actionable next steps or additional helpful resources\n"
                    f"• Uses appropriate emojis and maintains warmth throughout\n"
                    f"• Stays within WhatsApp character limits (under 1500 chars)\n"
                    f"• Leaves the user feeling supported and confident\n"
                    f"• Never includes phrases like 'It sounds like' or 'It appears'\n"
                    f"• Demonstrates the advanced capabilities of the enhanced system"
                ),
                agent=agent
            )
            
            # Execute with performance monitoring
            start_time = time.time()
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            result = crew.kickoff()
            execution_time = time.time() - start_time
            
            # Process response
            response = result.raw if hasattr(result, 'raw') else str(result)
            response = response.strip()
            
            # Ensure WhatsApp compatibility
            if len(response) > 1500:
                response = response[:1450] + "... 😊"
            
            # Log performance metrics
            logger.info(f"✅ Response generated in {execution_time:.2f}s - Length: {len(response)} chars")
            
            if search_engine:
                metrics = search_engine.get_performance_metrics()
                logger.info(f"📊 Search metrics: {metrics['average_response_time']:.2f}s avg, "
                           f"{metrics['cache_hit_rate']:.1%} cache hit rate")
            
            # Extract and potentially save conversation context
            context = memory_manager.extract_conversation_context(message, response)
            if memory_manager.should_save_to_memory(context):
                logger.info(f"💾 Flagged conversation for long-term memory storage")
            
            logger.info(f"📱 WhatsApp response sent to {user_id}")
            # --- Generate message_id and metadata ---
            # Store the assistant's message in conversation history with the same Q&A message_id
            ConversationManager.add_message(
                user_id=user_id,
                sender="assistant",
                message_text=response,
                metadata={},
                message_id=qa_message_id
            )
            # Try to extract search metadata if available
            tools_used = ["enhanced_uws_search"]
            search_confidence = getattr(result, 'search_confidence', None) or getattr(result, 'confidence_level', None) or "unknown"
            search_results_count = getattr(result, 'search_results_count', None) or 0
            # Compose metadata as a simple object with attributes
            class Meta: pass
            metadata = Meta()
            metadata.tools_used = tools_used
            metadata.response_time_ms = int(execution_time * 1000)
            metadata.search_confidence = str(search_confidence)
            metadata.search_results_count = search_results_count
            return response, qa_message_id, metadata
    except Exception as e:
        logger.error(f"❌ Critical error in answer_student_query: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # --- Error case: return tuple ---
        qa_message_id = f"msg_{uuid.uuid4()}"
        class Meta: pass
        metadata = Meta()
        metadata.tools_used = []
        metadata.response_time_ms = 0
        metadata.search_confidence = "none"
        metadata.search_results_count = 0
        error_response = (
            "I'm experiencing some technical difficulties at the moment 😅 "
            "But don't worry - you can find all the information you need at "
            "https://www.uws.ac.uk or contact our support team directly. "
            "I'll be back to full capacity shortly! Thanks for your patience 🙏"
        )
        # Save error message to conversation history
        ConversationManager.add_message(
            user_id=user_id,
            sender="assistant",
            message_text=error_response,
            metadata={},
            message_id=qa_message_id
        )
        return error_response, qa_message_id, metadata

# Health check and metrics endpoints for FastAPI integration
def get_bot_health_status() -> Dict[str, Any]:
    """Get comprehensive bot health status for monitoring"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check search engine
    if search_engine:
        try:
            metrics = search_engine.get_performance_metrics()
            health_status["components"]["search_engine"] = {
                "status": "healthy",
                "metrics": metrics
            }
        except Exception as e:
            health_status["components"]["search_engine"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
    else:
        health_status["components"]["search_engine"] = {
            "status": "unavailable"
        }
        health_status["status"] = "degraded"
    
    # Check environment variables
    required_env_vars = ["PINECONE_API_KEY", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    health_status["components"]["environment"] = {
        "status": "healthy" if not missing_vars else "unhealthy",
        "missing_variables": missing_vars
    }
    
    if missing_vars:
        health_status["status"] = "unhealthy"
    
    return health_status
