import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.visualization.schema_models import *

class Table:
    """Represent a normalized relational table.

    Assumptions:
        - `p_key` contains flattened primary-key columns used as identifiers and foreign-key anchors.
        - `attribs` contains visible non-derived columns and subsequently added foreign-key columns.

    Expected behavior:
        - Primary keys and attributes can be replaced or appended without changing the table name.

    Raises:
        - No custom exceptions; invalid calls generally result from misuse by callers.
    """

    # Store atomic attributes, flattened composites, foreign keys, and flattened primary keys.
    def __init__(self, name : str = ""):
        """Initialize an empty table.

        Assumptions:
            - The table name is known and unique in the registry.
        """
        self.name = name
        self.p_key = []
        self.attribs = []

    def setPrimaryKey(self, p_k : list[str]):
        """Replace the table's primary-key list.

        Assumptions:
            - `p_k` contains flattened keys normalized to this table's column names.
        """
        self.p_key = p_k[:]
    
    def addAttribs(self, attribs : list[str]):
        """Append one or more visible table attributes.

        Assumptions:
            - The input contains attribute names to show in the relational representation.
        """
        self.attribs.extend(attribs)


class Reference:
    """Model an FK relationship between one source attribute set and one destination attribute set."""

    def __init__(self, source_table, source_attribs, dest_table, dest_attribs):
        """Store a normalized relationship edge.

        Assumptions:
            - `source_attribs` and `dest_attribs` are corresponding, ordered attribute lists.
            - This class stores foreign-key references without validating their shape.
        """
        self.source_table : Table = source_table
        self.source_attrib : list[str] = source_attribs[:]

        self.dest_table : Table = dest_table
        self.dest_attrib : list[str] = dest_attribs[:]
        

class TableRegistry:
    """Build and maintain a schema's tables and foreign-key references.

    Assumptions:
        - The schema is validated and all participating entities exist.
        - Call `fromSchema()` once before rendering or inspection.

    Raises:
        - `ValueError`: for invalid relationship kinds or unsupported cardinalities.
    """
    
    def __init__(self):
        """Create an empty registry ready to be populated by the schema conversion logic."""
        self.tables : dict[str, Table] = {}
        self.refs : list[Reference] = []

    def _fk_name(self, target_key: str, link: Link | None = None) -> str:
        """Generate a stable foreign-key name, preferring the link role.

        Assumptions:
            - The relationship link provides the foreign key's role and table context.
            - The link's table name is the fallback when no role is set.

        Expected behavior:
            - Returns `<role>_<target_key>` or, without a role, `<source_table>_<target_key>`.

        Raises:
            - No exceptions; malformed links are handled defensively.
        """
        role = None
        source_table = link.entity if link is not None else ""

        if link is not None and getattr(link, "role", None):
            role = link.role.strip()

        if role:
            return f"{role}_{target_key}"

        return f"{source_table}_{target_key}"

    def __flattenAttrib(self, attrib : Attribute, added_pref : str = "") -> list[str]:
        """Flatten nested attributes into leaf names.

        Assumptions:
            - Composite attributes expand recursively using their field names and the supplied prefix.
            - String members are leaf names and are not expanded.
        """
        prefix = (added_pref + "_") if added_pref != "" else ""
        if not attrib.composite:
            return [prefix + attrib.name]
        res = []
        for part in attrib.composite:
            if (isinstance(part, str)):
                res.append(prefix + attrib.name + "_" + part)
            else:
                res.extend(self.__flattenAttrib(part, prefix + attrib.name))
        return res


    def addEntity(self, entity : Entity):
        """Create a base table for an entity.

        Assumptions:
            - Entity attributes are normalized by the schema model.
            - Derived attributes are omitted because they are not stored.
            - Multivalued attributes are handled separately, not in the base table.

        Raises:
            - `ValueError`: if required entity fields are missing or malformed.
        """
        # Add atomic attributes and flattened composites first.
        basic_table : Table = Table(entity.name)
        p_key = None
        for attr in entity.attributes:
            if attr.isDerived:
                continue

            if attr.isPrimaryKey or attr.isPartialKey:
                p_key = attr
            
            if attr.isMultiValued:
                continue
            else:
                basic_table.addAttribs(self.__flattenAttrib(attr))

        if p_key:
            basic_table.setPrimaryKey(self.__flattenAttrib(p_key))
        
        self.tables[entity.name] = basic_table
        

    # Add a multivalued attribute and link to its owning table.
    def addMultiValued(self, table_name : str, attr: Attribute):
        """Create a table for a multivalued attribute, preserving its owner's key.

        Assumptions:
            - The owning table exists in the registry and contains the source key(s).

        Raises:
            - `KeyError`: if the owning table is missing from the registry.
            - `ValueError`: if the attribute definition is malformed.
        """
        new_table : Table = Table(table_name + "_" + attr.name + "s")

        new_table.addAttribs(self.tables[table_name].p_key)
        new_table.addAttribs(self.__flattenAttrib(attr))  # Add all parts of the multivalued attribute.

        new_table.setPrimaryKey(new_table.attribs)
        # consider all attribs in the multivalued table as the pkey if no partial key was given
        self.tables[new_table.name] = new_table
        self.refs.append(Reference(new_table,
                                   self.tables[table_name].p_key,
                                   self.tables[table_name],
                                   self.tables[table_name].p_key))

    # Participating tables must already be registered.
    def addIdentifying(self, relation : Relationship):
        """Map an identifying relationship to its weak-entity table.

        Assumptions:
            - `relation.identifies` marks the relationship and names its weak entity.
            - Participating tables already exist in the registry.

        Expected behavior:
            - The weak entity receives the identifying key columns; relationship attributes join the appropriate table.

        Raises:
            - `ValueError`: if the relationship does not carry an identifying entity.
        """
        if not relation.identifies:
            raise ValueError("this method should only be called on identifying relationships")
        
        identified = relation.identifies[0]
        
        relation_attribs = []
        multivalued_attribs = []

        for attr in relation.attributes:
            if attr.isDerived:
                continue

            if attr.isMultiValued:
                multivalued_attribs.append(attr)
                continue  # Add multivalued attributes later.

            relation_attribs.extend(self.__flattenAttrib(attr))

        # Handle binary identifying relationships like 1:1 relationships.
        if len(relation.links) == 2:
            
            first = relation.links[0]
            second = relation.links[1]

            first_table = self.tables[first.entity]
            second_table = self.tables[second.entity]

            if identified == first.entity:
                added_attribs = [self._fk_name(tok, second) for tok in second_table.p_key]
                first_table.addAttribs(added_attribs)

                self.refs.append(Reference(first_table, 
                                            added_attribs, 
                                            second_table, second_table.p_key))
                first_table.addAttribs(relation_attribs)
                for attr in multivalued_attribs:
                    self.addMultiValued(first_table.name, attr)

            else:
                added_attribs = [self._fk_name(tok, first) for tok in first_table.p_key]
                second_table.addAttribs(added_attribs)
                self.refs.append(Reference(second_table, 
                                            added_attribs,
                                            first_table, first_table.p_key))
                second_table.addAttribs(relation_attribs)
                for attr in multivalued_attribs:
                    self.addMultiValued(second_table.name, attr)

        # Handle n-ary identifying relationships.
        else:   
            self.addNary(relation)
            # `addNary()` handles the identifying link.
            
    # Add a binary 1:1 relationship.
    def addOneToOne(self, relation : Relationship):
        """Map a binary 1:1 relationship.

        Assumptions:
            - Exactly two links are present, both with cardinality `1`.
            - Participation determines which side receives the foreign key.

        Raises:
            - `ValueError`: if the relationship is not a binary 1:1 link set.
        """
        if len(relation.links) != 2 or \
            relation.links[0].cardinality != '1' or relation.links[1].cardinality != '1':
            raise ValueError("addOneToOne only works on binary 1:1 relationships")
        
        first = relation.links[0]
        second = relation.links[1]

        first_table = self.tables[first.entity]
        second_table = self.tables[second.entity]

        relation_attribs = []
        multival_attribs = []
        for attr in relation.attributes:
            if attr.isMultiValued:
                multival_attribs.append(attr)
                continue
            relation_attribs.extend(self.__flattenAttrib(attr))

        if first.participation == 'total':
            added_attribs = [self._fk_name(tok, second) for tok in second_table.p_key]
            first_table.addAttribs(added_attribs)
            self.refs.append(Reference(first_table, 
                                       added_attribs, 
                                       second_table, second_table.p_key))
            first_table.addAttribs(relation_attribs)
            for attr in multival_attribs:
                self.addMultiValued(first_table.name, attr)
        else:
            added_attribs = [self._fk_name(tok, first) for tok in first_table.p_key]
            second_table.addAttribs(added_attribs)
            self.refs.append(Reference(second_table, 
                                       added_attribs,
                                       first_table, first_table.p_key))
            second_table.addAttribs(relation_attribs)
            for attr in multival_attribs:
                self.addMultiValued(second_table.name, attr)
        
    # Add a binary 1:N relationship.
    def addOneToMany(self, relation : Relationship):
        """Map a binary 1:N relationship.

        Assumptions:
            - Exactly two links are present; one has cardinality `1` and the other does not.
            - The standard mapping places the foreign key in the table on the `N` side.

        Raises:
            - `ValueError`: if the relationship is not a binary 1:N link set.
        """
        if len(relation.links) != 2:
            raise ValueError("addOneToMany only works on binary 1:N relationships")
        
        first = relation.links[0]
        second = relation.links[1]

        first_table = self.tables[first.entity]
        second_table = self.tables[second.entity]

        relation_attribs = []
        multival_attribs = []
        for attr in relation.attributes:
            if attr.isMultiValued:
                multival_attribs.append(attr)
                continue
            relation_attribs.extend(self.__flattenAttrib(attr))


        if first.cardinality == 'N':
            added_attribs = [self._fk_name(tok, second) for tok in second_table.p_key]
            first_table.addAttribs(added_attribs)
            self.refs.append(Reference(first_table, 
                                       added_attribs, 
                                       second_table, second_table.p_key))

            first_table.addAttribs(relation_attribs)
            for attr in multival_attribs:
                self.addMultiValued(first_table.name, attr)
        else:
            added_attribs = [self._fk_name(tok, first) for tok in first_table.p_key]
            second_table.addAttribs(added_attribs)
            self.refs.append(Reference(second_table, 
                                       added_attribs,
                                       first_table, first_table.p_key))
            second_table.addAttribs(relation_attribs)
            for attr in multival_attribs:
                self.addMultiValued(second_table.name, attr)
    
    # Add an N:M relationship or its multivalued attributes.
    def addManyToMany(self, relation : Relationship):
        """Create a junction table for a binary many-to-many relationship.

        Assumptions:
            - Exactly two links are present; neither has cardinality `1`.
            - The key combines both entity keys; relationship attributes are stored alongside them.

        Raises:
            - `ValueError`: if the relationship is not a binary M:N relationship.
        """
        if len(relation.links) != 2:
            raise ValueError("addManyToMany only works on binary M:N relationships")
        
        first = relation.links[0]
        second = relation.links[1]

        first_table = self.tables[first.entity]
        second_table = self.tables[second.entity]

        rel_table = Table(relation.name)

        normalized_first_pkey = [self._fk_name(tok, first) for tok in first_table.p_key]
        normalized_second_pkey = [self._fk_name(tok, second) for tok in second_table.p_key]

        # Add relationship attributes.
        added_attribs = []
        added_attribs.extend(normalized_first_pkey + normalized_second_pkey)

        rel_table.setPrimaryKey(added_attribs)
        self.tables[rel_table.name] = rel_table

        for attr in relation.attributes:
            if attr.isMultiValued:
                self.addMultiValued(rel_table.name, attr)
            else:
                added_attribs.extend(self.__flattenAttrib(attr))

        # Link the junction table to both entity tables.
        self.refs.append(Reference(rel_table,
                                   normalized_first_pkey,
                                   first_table, first_table.p_key))
        
        self.refs.append(Reference(rel_table,
                                   normalized_second_pkey,
                                   second_table, second_table.p_key))


        self.tables[rel_table.name].addAttribs(added_attribs)
        # Add atomic attributes and flattened composites to the relationship table.
    

    def addNary(self, relation : Relationship):
        """Create a relationship table for an n-ary relation.

        Assumptions:
            - The relationship has more than two participating links.
            - Strong entities contribute their primary keys to the relation table, while an identifying entity may enrich or absorb that relationship table.

        Raises:
            - `ValueError`: if the relationship degree is not greater than two.
        """

        if len(relation.links) <= 2:
            raise ValueError("addNary works on relations with degree more than 2")
        identified = relation.identifies[0] if relation.identifies else None

        p_keys = []
        relation_attribs = []
        multivalued_attribs = []

        for attr in relation.attributes:
            if attr.isDerived:
                continue

            if attr.isMultiValued:
                multivalued_attribs.append(attr)
                continue  # Add multivalued attributes later.

            relation_attribs.extend(self.__flattenAttrib(attr))

        def isStrong(link : Link):
                return link.entity != identified
            
        strong_links = list(filter(isStrong, relation.links))
        for link in strong_links:
            added_pkeys = [self._fk_name(tok, link) for tok in self.tables[link.entity].p_key]
            p_keys.append(added_pkeys)
            # Link the relationship table to this entity.

        table_name = relation.name
        rel_table = Table(table_name)

        
        # Connect the table to each strong entity and add its corresponding attributes.
        for p_key, link in zip(p_keys, strong_links):
            rel_table.addAttribs(p_key)
            self.refs.append(Reference(rel_table, 
                                    p_key, 
                                    self.tables[link.entity], self.tables[link.entity].p_key))

        
        rel_table.setPrimaryKey(rel_table.attribs) 

        if identified:
            self.tables[identified].addAttribs(rel_table.attribs)
            self.tables[identified].setPrimaryKey(self.tables[identified].p_key + rel_table.attribs)
        # The table currently contains only strong-entity primary keys.

        rel_table.addAttribs(relation_attribs)
        # Add simple attributes and flattened composites.

        self.tables[table_name] = rel_table
        # Register the relationship table.

        for attr in multivalued_attribs:
            self.addMultiValued(table_name, attr)
        # Add multivalued attributes.
        
        if identified:
            self.refs.append(Reference(self.tables[identified],
                                    rel_table.p_key,
                                    rel_table,
                                    rel_table.p_key))
    
    def fromSchema(self, schema : Schema):
        """Convert a schema into a normalized relational registry.

        Assumptions:
            - The schema model has validated all entities and relationships.
            - Identifying relationships run first to establish weak-entity keys.

        Expected behavior:
            - Add entities first, resolve identifying relationships, then map standard binary or n-ary relationships.

        Raises:
            - `ValueError`: if a relationship kind is unsupported or a schema reference is invalid.
        """

        # Add strong and weak entities; weak keys may be incomplete.
        # Add atomic attributes and flattened composites; handle multivalued attributes later.
        for entity in schema.entities:
            self.addEntity(entity)

        identifying_relations = list(filter(lambda relation : relation.identifies, schema.relationships))
        standard_relations = list(filter(lambda relation : not relation.identifies, schema.relationships))

        # Resolve identifying relationships first to establish all entity keys.
        for relation in identifying_relations:
            self.addIdentifying(relation)

        # Map remaining relationships, including their attributes.
        for relation in standard_relations:
            if len(relation.links) == 2:
                first_cardinality = relation.links[0].cardinality
                second_cardinality = relation.links[1].cardinality
                if first_cardinality == '1' and second_cardinality == '1':
                    self.addOneToOne(relation)
                elif first_cardinality == '1' or second_cardinality == '1':
                    self.addOneToMany(relation)
                else:
                    self.addManyToMany(relation)
            else:
                self.addNary(relation)

        for entity in schema.entities:
            for attr in entity.attributes:
                if not attr.isMultiValued or attr.isDerived: 
                    continue
                self.addMultiValued(entity.name, attr)






