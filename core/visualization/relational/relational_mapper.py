import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.visualization.schema_models import *

class Table:
    """Represent a normalized relational table.

    Assumptions:
        - `p_key` stores only the flattened primary-key columns to be used as identifiers and foreign-key anchors.
        - `attribs` stores the visible non-derived columns plus any foreign-key columns that were added later.

    Expected behaviour:
        - Primary keys and additional attribute columns can be appended or replaced without disturbing the table name.

    Raises:
        - No custom exceptions are raised by this class itself; invalid calls usually come from type misuse outside the class.
    """

    # keeps track of atomic attribs or (flattened composites and fkeys) and (flattened primary key) only
    def __init__(self, name : str = ""):
        """Initialize an empty table shell.

        Assumptions:
            - The table name is already known and is unique within the registry.
        """
        self.name = name
        self.p_key = []
        self.attribs = []

    def setPrimaryKey(self, p_k : list[str]):
        """Replace the table's primary-key list.

        Assumptions:
            - `p_k` is a list of flattened keys already normalized to the table's column names.
        """
        self.p_key = p_k[:]
    
    def addAttribs(self, attribs : list[str]):
        """Append one or more visible table attributes.

        Assumptions:
            - The input is a list of attribute names that should be visible in the final relational representation.
        """
        self.attribs.extend(attribs)


class Reference:
    """Model an FK relationship between one source attribute set and one destination attribute set."""

    def __init__(self, source_table, source_attribs, dest_table, dest_attribs):
        """Store a normalized relationship edge.

        Assumptions:
            - `source_attribs` and `dest_attribs` are lists of attributes in matching order.
            - This class is used to render foreign-key references and does not validate shape beyond assignment.
        """
        self.source_table : Table = source_table
        self.source_attrib : list[str] = source_attribs[:]

        self.dest_table : Table = dest_table
        self.dest_attrib : list[str] = dest_attribs[:]
        

class TableRegistry:
    """Build and maintain the set of relational tables and foreign-key references for a schema.

    Assumptions:
        - The schema has already been validated and all participating entities exist.
        - `fromSchema()` is called once to populate the registry before rendering or inspection.

    Raises:
        - `ValueError`: for invalid relationship kinds or unsupported cardinality combinations in the conversion logic.
    """
    
    def __init__(self):
        """Create an empty registry ready to be populated by the schema conversion logic."""
        self.tables : dict[str, Table] = {}
        self.refs : list[Reference] = []

    def _fk_name(self, target_key: str, link: Link | None = None) -> str:
        """Generate a stable foreign-key attribute name using the link role if present.

        Assumptions:
            - For a given foreign key, the relationship link itself carries the semantic role and table context.
            - If no role is present, the table name used by the link acts as the fallback.

        Expected behaviour:
            - Returns `<role>_<target_key>` when a role exists; otherwise `<source_table>_<target_key>`.

        Raises:
            - No exception is raised here; malformed link objects are simply handled defensively.
        """
        role = None
        source_table = link.entity if link is not None else ""

        if link is not None and getattr(link, "role", None):
            role = link.role.strip()

        if role:
            return f"{role}_{target_key}"

        return f"{source_table}_{target_key}"

    def __flattenAttrib(self, attrib : Attribute, added_pref : str = "") -> list[str]:
        """Flatten a nested attribute structure into a list of leaf attribute names.

        Assumptions:
            - Composite attributes are recursively expanded using their contained field names and the supplied prefix.
            - String members of a composite attribute are treated as leaf names and do not recurse further.
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
        """Create a base table for a regular entity.

        Assumptions:
            - Entity attributes are already normalized by the schema model.
            - Derived attributes are ignored because they are not physically stored.
            - Multi-valued attributes are not kept in the base entity table but are handled separately.

        Raises:
            - `ValueError`: if the entity object is malformed and cannot be processed without required fields.
        """
        # first atomic attribs and flattened composites
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
        

    # adds a multivalue attribute and link to table denoted by table_name
    def addMultiValued(self, table_name : str, attr: Attribute):
        """Create a separate table for a multivalued attribute and preserve its owning table's key.

        Assumptions:
            - The owning table already exists in the registry and contains the source key(s).

        Raises:
            - `KeyError`: if the owning table is missing from the registry.
            - `ValueError`: if the attribute definition is malformed.
        """
        new_table : Table = Table(table_name + "_" + attr.name + "s")

        new_table.addAttribs(self.tables[table_name].p_key)
        new_table.addAttribs(self.__flattenAttrib(attr)) # all parts of this multivalued attrib

        new_table.setPrimaryKey(new_table.attribs)
        # consider all attribs in the multivalued table as the pkey if no partial key was given
        self.tables[new_table.name] = new_table
        self.refs.append(Reference(new_table,
                                   self.tables[table_name].p_key,
                                   self.tables[table_name],
                                   self.tables[table_name].p_key))

    # all tables related should already be created and registered
    def addIdentifying(self, relation : Relationship):
        """Convert an identifying relationship into a weak-entity-aware table change.

        Assumptions:
            - The relationship is already marked as identifying and points to a weak entity via `relation.identifies`.
            - The participating tables already exist in the registry.

        Expected behaviour:
            - The identifying entity receives the identifying table's key columns and the relationship attributes are folded into the appropriate table.

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
                continue #will be added later

            relation_attribs.extend(self.__flattenAttrib(attr))

        # Binary identifying relations
        # Extremely similar logic to creating a 1:1 Relation
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

        # N-ary identifying relations
        else:   
            self.addNary(relation)
            # handles the existence of identifying link within
            
    # adds binary 1:1 relationship
    def addOneToOne(self, relation : Relationship):
        """Apply the conversion rules for a binary 1:1 relationship.

        Assumptions:
            - Exactly two links are present and both have cardinality `1`.
            - The total/partial participation flag decides which side gets the foreign key column.

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
        
    # adds binary 1:N relationship
    def addOneToMany(self, relation : Relationship):
        """Apply the conversion rules for a binary 1:N relationship.

        Assumptions:
            - Exactly two links are present and one is cardinality `1` while the other is not.
            - The side with cardinality `N` keeps the foreign key on the other table in the standard relational mapping.

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
    
    # adds N:M relations or relations with optional MultiValue attribs
    def addManyToMany(self, relation : Relationship):
        """Create a junction table for a binary many-to-many relationship.

        Assumptions:
            - Exactly two links are present and neither is cardinality `1`.
            - The relationship key is the union of the two entity keys, with extra relationship attributes stored beside them.

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

        # add relation attribs
        added_attribs = []
        added_attribs.extend(normalized_first_pkey + normalized_second_pkey)

        rel_table.setPrimaryKey(added_attribs)
        self.tables[rel_table.name] = rel_table

        for attr in relation.attributes:
            if attr.isMultiValued:
                self.addMultiValued(rel_table.name, attr)
            else:
                added_attribs.extend(self.__flattenAttrib(attr))

        # add links to both tables
        self.refs.append(Reference(rel_table,
                                   normalized_first_pkey,
                                   first_table, first_table.p_key))
        
        self.refs.append(Reference(rel_table,
                                   normalized_second_pkey,
                                   second_table, second_table.p_key))


        self.tables[rel_table.name].addAttribs(added_attribs)
        # add all atomic and flattened attribs to relation table
    

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
                continue #will be added later

            relation_attribs.extend(self.__flattenAttrib(attr))

        def isStrong(link : Link):
                return link.entity != identified
            
        strong_links = list(filter(isStrong, relation.links))
        for link in strong_links:
            added_pkeys = [self._fk_name(tok, link) for tok in self.tables[link.entity].p_key]
            p_keys.append(added_pkeys)
            # add link between relation table and entity that it connects to

        table_name = relation.name
        rel_table = Table(table_name)

        
        # now we have the table and we can connect the links to all strong entities connected and add corr attribs to th table
        for p_key, link in zip(p_keys, strong_links):
            rel_table.addAttribs(p_key)
            self.refs.append(Reference(rel_table, 
                                    p_key, 
                                    self.tables[link.entity], self.tables[link.entity].p_key))

        
        rel_table.setPrimaryKey(rel_table.attribs) 

        if identified:
            self.tables[identified].addAttribs(rel_table.attribs)
            self.tables[identified].setPrimaryKey(self.tables[identified].p_key + rel_table.attribs)
        # at this point it's only the primary keys of all srong entities

        rel_table.addAttribs(relation_attribs)
        # then we add simple and flattened composites

        self.tables[table_name] = rel_table
        # add relation table to registry

        for attr in multivalued_attribs:
            self.addMultiValued(table_name, attr)
        # we add multivalued attribs
        
        if identified:
            self.refs.append(Reference(self.tables[identified],
                                    rel_table.p_key,
                                    rel_table,
                                    rel_table.p_key))
    
    def fromSchema(self, schema : Schema):
        """Convert an entire schema into a normalized relational registry.

        Assumptions:
            - Entities and relationships are already validated by the schema model.
            - Identifying relationships are processed first so weak-entity keys are in place before standard relationships are applied.

        Expected behaviour:
            - Strong entities are emitted first, then identifying relationships are resolved, followed by standard binary or n-ary relationship mapping.

        Raises:
            - `ValueError`: if any relationship kind is unsupported or if a schema reference is invalid.
        """

        strong_entities = []
        weak_entities = []

        # first add strong entities and weak entities (without full pkey) 
        # adds atomic and cflattened composites as well but multivalued needs to be handled later
        for entity in schema.entities:
            if entity.isWeak:
                weak_entities.append(entity)
            else:
                strong_entities.append(entity)
            self.addEntity(entity)

        identifying_relations = list(filter(lambda relation : relation.identifies, schema.relationships))
        standard_relations = list(filter(lambda relation : not relation.identifies, schema.relationships))

        # resolve identifying relations first so that we guarantee that all entities have their pkeys set
        for relation in identifying_relations:
            self.addIdentifying(relation)

        # resolves the rest of relations automatically handling all relation attribs
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






