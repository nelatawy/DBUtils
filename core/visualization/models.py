from __future__ import annotations
import re
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

class Attribute(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="The identifier name of the attribute. Keep it concise, camelCase or PascalCase, no generic spaces.",
    )
    isPrimaryKey: bool = Field(
        default= False,
        description="Set to true ONLY if this attribute uniquely identifies the parent Entity.",
    )
    isPartialKey: bool = Field(
        default= False,
        description="Set to true ONLY if this attribute is a partial key for this weak entity"
    )
    isMultiValued: bool = Field(
        default= False,
        description="Set to true if an instance can contain multiple values for this attribute",
    )
    isDerived: bool = Field(
        default= False,
        description="Set to true if the attribute value is an aggregate that can be calculated or pulled from other attributes.",
    )
    composite: list[Attribute | str] = Field(
        default=[],
        description="If this attribute is made of smaller parts, name them here.",
    )

    # make sure the parsed object is valid by enforcing some constraints
    @model_validator(mode="after")
    def check_attribute_logic(self) -> Attribute:
        if self.isPrimaryKey and self.isMultiValued:
            raise ValueError("Primary key can't be multivalued")
        
        if self.isPrimaryKey and self.isPartialKey:
            raise ValueError("Primary key can't be a partial key")
        
        if not self.name.strip():
            raise ValueError("Attribute must have a name")
        return self
    #list of names of attributes involved
    # can also be swapped for list[Attribute] to allow for recursive and more complex compositions
    
    # we must use Attribute.model_rebuild() to resolve forward definition

Attribute.model_rebuild()


    
class Entity(BaseModel): 
    name: str = Field(
        ...,
        min_length=1,
        description="The singular name of the Entity",
    )
    isWeak : bool = Field(
        default=False,
        description="declares wether or not the entity is a weak entity"
    )
    attributes: list[Attribute] = Field(
        ...,
        description="Collection of fields and attributes assigned to this Entity",
    )
    # make sure the parsed object is valid by enforcing some constraints
    @model_validator(mode="after")
    def check_attribute_logic(self) -> Entity:
        if not self.name.strip():
            raise ValueError("Entity must have a name")
        
        hasPrimaryKey = False
        for attr in self.attributes:
            if attr.isPartialKey and not self.isWeak:
                raise ValueError("can't have a partial key for a non-weak entity")
            if attr.isPrimaryKey:
                hasPrimaryKey = True

        if not hasPrimaryKey and not self.isWeak:
            raise ValueError("Entity doesn't have a primary key and isn't declared as a weak entity")
        
        return self

class Link(BaseModel):
    entity : str = Field(
        ...,
        min_length=1,
        description="name of the participating entity"
    )
    cardinality : str = Field(
        ...,
        description="specifies cardinality of this entity in this relationship can be either 1 or a char identifier like M or N"
    )
    participation : Literal["total", "partial"] = Field(
        default="partial",
        description="participation type either 'total' or 'partial'"
    )
    role: Optional[str] = Field(
        default=None,
        description="Optional semantic role for this side of the relationship, used when naming generated foreign keys."
    )
    @model_validator(mode="after")
    def check_attribute_logic(self) -> Link:
        if not re.match(r'^[1a-zA-Z]$', self.cardinality):
            raise ValueError(
                f"Invalid cardinality structural token '{self.cardinality}'. "
                "Must be '1' or a dynamic mapping variable letter like 'N', 'M'."
            )
        if self.role is not None and not self.role.strip():
            raise ValueError("Link role must not be empty when provided")
        
        return self

class Relationship(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="The verb phrase representing the relationship link (e.g., 'Works_In', 'Manages').",
    )
    links: list[Link] = Field(
        ...,
        description="Each link describes one participating entity, its cardinality, and its participation type."
    )
    
    identifies : list[str] = Field(
        default= [],
        description= "declares the entities that this relationship identifies"
    )

    attributes: list[Attribute] = Field(
        default=[],
        description="Optional field to store descriptive qualities native to the relationship link itself.",
    )

    @model_validator(mode="after")
    def check_attribute_logic(self) -> Relationship:
        if not self.name.strip():
            raise ValueError("Relationship must have a name")
        if len(self.links) < 2:
            raise ValueError("Relationships must have a degree at least 2")
        
        return self

    
class Schema(BaseModel):
    entities : list[Entity] = Field(
        ...,
        description="lists all entities that exist in the schema"
    )
    relationships: list[Relationship] = Field(
        ...,
        description="lists all relationships connecting existing entities"
    )

    @model_validator(mode="after")
    def check_attribute_logic(self) -> Schema:
        entity_set = set() #for faster checks later
        unidentified_entities = set()

        for entity in self.entities:
            if entity.name in entity_set:
                raise ValueError("Duplicate Entities with the same name")
            
            if entity.isWeak:
                unidentified_entities.add(entity.name)

            entity_set.add(entity.name)

        for relationship in self.relationships :
            for link in relationship.links:
                if link.entity not in entity_set:
                    raise ValueError(f"Undefined Entity referenced in relationship {relationship.name}")
            
            for entity in relationship.identifies:
                if entity in unidentified_entities:
                    unidentified_entities.remove(entity)
        
        if len(unidentified_entities) > 0:
            raise ValueError("Weak entity is not identified by any relationship")
        return self