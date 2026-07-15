import io
import pandas as pd
from typing import List
from pipelines.ingestion.base import ExtractedPage


def extract_csv(file_bytes: bytes) -> List[ExtractedPage]:
    pages: List[ExtractedPage] = []
    df = pd.read_csv(io.BytesIO(file_bytes))
    
    if len(df) <= 1000:
        # Small CSV: full markdown
        md = df.to_markdown(index=False)
        pages.append(ExtractedPage(
            page_number=1,
            content=md,
            content_type="table",
            metadata={"row_count": len(df), "column_count": len(df.columns)}
        ))
    else:
        # Large CSV: summary + sample blocks
        summary_parts = []
        summary_parts.append(f"# CSV Summary\n")
        summary_parts.append(f"## Columns: {list(df.columns)}\n")
        
        # Numeric column stats
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            summary_parts.append("\n## Numeric Column Stats:\n")
            summary_parts.append(df[numeric_cols].describe().to_markdown())
        
        # Categorical column top 5
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            top5 = df[col].value_counts().head(5)
            summary_parts.append(f"\n## Top 5 values for {col}:\n")
            summary_parts.append(top5.to_markdown())
        
        summary_content = "\n".join(summary_parts)
        pages.append(ExtractedPage(
            page_number=1,
            content=summary_content,
            content_type="text",
            metadata={"type": "summary", "row_count": len(df)}
        ))
        
        # Sample 100-row blocks
        block_size = 100
        for block_num, start_row in enumerate(range(0, len(df), block_size), 2):
            end_row = min(start_row + block_size, len(df))
            block_df = df.iloc[start_row:end_row]
            block_md = block_df.to_markdown(index=False)
            pages.append(ExtractedPage(
                page_number=block_num,
                content=block_md,
                content_type="table",
                metadata={"start_row": start_row, "end_row": end_row}
            ))
    
    return pages
