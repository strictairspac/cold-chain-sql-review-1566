from pydantic import BaseModel,Field
class ReversalInput(BaseModel):
    reason:str=Field(min_length=2,max_length=200)
