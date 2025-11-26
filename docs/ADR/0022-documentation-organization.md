# ADR 0022: Documentation and Repository Organization

**Status**: Accepted  
**Date**: 2025-11-27  
**Decision Makers**: Development Team  
**Related ADRs**: All previous ADRs

---

## Context

As the Checkpoint project has grown from a simple e-commerce system to a comprehensive platform with Flash Sales, Partner Integration, RMA workflows, Observability, and now Order Filtering, Low Stock Alerts, and Notifications, the documentation and repository structure needs systematic organization to remain maintainable.

### Current State (Before Checkpoint 4)

**Documentation:**
- 21+ ADRs in `docs/ADR/` (some numbered inconsistently: 009, 0020, etc.)
- UML diagrams in `docs/UML/` (single markdown file)
- Feature-specific docs scattered in root: `ADMIN_PAGES.md`, `INVENTORY_LOGIC.md`, `RMA_*.md`
- Implementation guides: `DOCKER.md`, `RMA_TESTING.md`
- Quick references: `DOCKER_QUICKREF.txt`, `RMA_QUICKSTART.md`

**Repository Structure:**
- Mixed root-level files (25+ markdown/text files)
- Module-based structure: `src/`, `tests/`, `migrations/`, `scripts/`, `db/`
- Docker-related: `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`
- Configuration: `requirements.txt`, `setup.py`, `Makefile`

### Problems Identified

1. **Documentation Discoverability**: Hard to find relevant docs (15+ files in root)
2. **ADR Numbering**: Inconsistent (009 vs 0009, gaps in sequence)
3. **Duplication**: Similar content in multiple files (RMA_QUICKSTART vs RMA_TESTING)
4. **Outdated Content**: Some docs reference Checkpoint 2 structures
5. **No Index**: No central navigation for documentation
6. **Mixed Concerns**: Feature docs mixed with operational guides
7. **No Contribution Guide**: No clear process for adding docs/features

---

## Decision

Implement a **structured documentation hierarchy** with **consistent naming** and **clear separation of concerns**.

### Documentation Organization

```
docs/
├── README.md                           # Documentation index (NEW)
├── ADR/                                # Architecture Decision Records
│   ├── README.md                       # ADR index with links (NEW)
│   ├── 0001-database-choice.md
│   ├── ...
│   ├── 0021-lightweight-features-design.md
│   └── 0022-documentation-organization.md
├── UML/                                # Architecture diagrams
│   ├── uml_views.md                    # 4+1 views
│   └── schema.html                     # Database schema
├── features/                           # Feature-specific documentation (NEW)
│   ├── flash-sales.md
│   ├── partner-integration.md
│   ├── rma-workflow.md
│   ├── observability.md
│   └── checkpoint4-features.md         # Order filtering, low stock, notifications
├── operations/                         # Deployment & operations (NEW)
│   ├── docker-setup.md
│   ├── docker-quickref.md
│   ├── database-migrations.md
│   └── monitoring.md
├── development/                        # Developer guides (NEW)
│   ├── CONTRIBUTING.md
│   ├── testing-guide.md
│   ├── code-style.md
│   └── local-setup.md
└── api/                                # API documentation (NEW)
    ├── rest-api.md
    ├── partner-api.md
    └── rma-api.md
```

### Root Directory Cleanup

**Keep in Root** (essential files only):
- `README.md` - Project overview with links to `docs/`
- `requirements.txt`, `setup.py`, `Makefile` - Build/dependency files
- `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh` - Container config
- `.gitignore`, `.env.example` - Version control and config templates

**Move to `docs/`**:
- All `.md` files except root README
- All `.txt` documentation files
- Consolidate similar guides

### ADR Numbering Convention

**Standard**: 4-digit zero-padded (0001, 0002, ..., 0099, 0100)

**Migration Plan**:
1. Rename `009-Circuit-Breaker-Pattern.md` → `0009-circuit-breaker-pattern.md`
2. Fill gaps: Create placeholder ADRs or renumber
3. Update all cross-references

**Naming Convention**:
```
<number>-<kebab-case-title>.md

Examples:
0021-lightweight-features-design.md
0022-documentation-organization.md
```

### Documentation Standards

#### 1. README Structure

**Root README.md**:
```markdown
# Checkpoint 4 - E-Commerce Platform

## Quick Start
[Docker setup in 2 minutes]

## Features
- Core Shopping
- Flash Sales
- Partner Integration
- RMA/Returns
- Observability
- Order Filtering (NEW)
- Low Stock Alerts (NEW)
- RMA Notifications (NEW)

## Documentation
- [Architecture & Design](docs/README.md)
- [API Reference](docs/api/)
- [Development Guide](docs/development/)
- [Operations Manual](docs/operations/)

## Testing
[How to run tests]

## Contributing
[Link to CONTRIBUTING.md]
```

**docs/README.md** (NEW):
```markdown
# Documentation Index

## Architecture
- [ADR Index](ADR/README.md) - All architecture decisions
- [UML Diagrams](UML/uml_views.md) - 4+1 views

## Features
- [Flash Sales](features/flash-sales.md)
- [Partner Integration](features/partner-integration.md)
- [RMA Workflow](features/rma-workflow.md)
- [Observability](features/observability.md)
- [Checkpoint 4 Features](features/checkpoint4-features.md)

## Operations
- [Docker Setup](operations/docker-setup.md)
- [Database Migrations](operations/database-migrations.md)
- [Monitoring](operations/monitoring.md)

## Development
- [Contributing Guide](development/CONTRIBUTING.md)
- [Testing Guide](development/testing-guide.md)
- [Local Setup](development/local-setup.md)

## API Reference
- [REST API](api/rest-api.md)
- [Partner API](api/partner-api.md)
- [RMA API](api/rma-api.md)
```

#### 2. ADR Template

Every ADR must follow this structure:

```markdown
# ADR NNNN: Title

**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Date**: YYYY-MM-DD
**Decision Makers**: [Team/Role]
**Related ADRs**: [Links to related ADRs]

## Context
[Problem statement and background]

## Decision
[What we decided to do]

## Consequences
### Positive
[Benefits]

### Negative
[Drawbacks]

## Alternatives Considered
[Other options and why they were rejected]

## References
[External links, related docs]
```

#### 3. Feature Documentation Template

```markdown
# Feature Name

## Overview
[High-level description]

## Business Value
[Why this feature exists]

## Architecture
[System design, components]

## User Guide
[How to use the feature]

## API Reference
[Endpoints, request/response]

## Configuration
[Environment variables, settings]

## Testing
[How to test this feature]

## Troubleshooting
[Common issues and solutions]

## Related Documentation
[Links to ADRs, UML, etc.]
```

---

## Implementation Plan

### Phase 1: Structure Creation (Week 1)

1. **Create Directory Structure**
   ```bash
   mkdir -p docs/{features,operations,development,api}
   ```

2. **Create Index Files**
   - `docs/README.md` - Main documentation index
   - `docs/ADR/README.md` - ADR listing with summaries
   - `docs/features/README.md` - Feature catalog

3. **Migrate Existing Documentation**
   ```bash
   # Move feature docs
   mv ADMIN_PAGES.md docs/features/admin-interface.md
   mv INVENTORY_LOGIC.md docs/features/inventory-management.md
   mv RMA_*.md docs/features/
   
   # Move operational docs
   mv DOCKER*.md docs/operations/
   mv DOCKER*.txt docs/operations/
   
   # Consolidate duplicates
   cat RMA_QUICKSTART.md RMA_TESTING.md > docs/features/rma-workflow.md
   ```

4. **Standardize ADR Numbering**
   ```bash
   mv docs/ADR/009-Circuit-Breaker-Pattern.md \
      docs/ADR/0009-circuit-breaker-pattern.md
   ```

### Phase 2: Content Consolidation (Week 2)

1. **Merge Duplicate Content**
   - `RMA_QUICKSTART.md` + `RMA_TESTING.md` → `docs/features/rma-workflow.md`
   - `DOCKER.md` + `DOCKER_QUICKREF.txt` → `docs/operations/docker-setup.md`
   - `RMA_API.md` + `RMA_IMPLEMENTATION_SUMMARY.md` → `docs/api/rma-api.md`

2. **Update Cross-References**
   - Find all `[link](../X.md)` references
   - Update to new paths
   - Use relative paths from document location

3. **Create Missing Documentation**
   - `docs/development/CONTRIBUTING.md` - How to contribute
   - `docs/development/testing-guide.md` - Testing best practices
   - `docs/api/rest-api.md` - Core API endpoints
   - `docs/features/checkpoint4-features.md` - New features guide

### Phase 3: Quality Assurance (Week 3)

1. **Verify All Links Work**
   ```bash
   # Use markdown-link-check or similar
   find docs -name "*.md" -exec markdown-link-check {} \;
   ```

2. **Spell Check All Documentation**
   ```bash
   # Use aspell or similar
   find docs -name "*.md" -exec aspell check {} \;
   ```

3. **Validate ADR Format**
   - Ensure all ADRs follow template
   - Check for required sections
   - Verify numbering sequence

4. **Review Content Accuracy**
   - Ensure docs match current implementation
   - Remove outdated sections
   - Add deprecation warnings where needed

---

## Documentation Maintenance Process

### Adding New Features

1. **Create Feature Document** in `docs/features/`
2. **Write ADR** documenting design decisions
3. **Update API Documentation** if new endpoints added
4. **Update UML Diagrams** to reflect new components
5. **Update Index Files** to link to new content
6. **Add Testing Section** to feature doc

### Updating Existing Features

1. **Update Feature Document** with changes
2. **Create New ADR** if architecture changes
3. **Mark Old ADR as "Superseded"** if replaced
4. **Update UML Diagrams** if structure changes
5. **Update API Docs** if endpoints change
6. **Update Changelog** in root README

### Deprecating Features

1. **Mark ADR as "Deprecated"** with deprecation date
2. **Add Deprecation Warning** to feature doc
3. **Update UML Diagrams** to show deprecated components
4. **Document Migration Path** in feature doc
5. **Set Removal Timeline** in deprecation notice

---

## Consequences

### Positive

**Improved Discoverability:**
- ✅ Structured hierarchy makes finding docs easier
- ✅ Clear separation of concerns (features vs operations vs development)
- ✅ Index files provide navigation
- ✅ Consistent naming enables predictable paths

**Better Maintainability:**
- ✅ Template ensures consistency
- ✅ Clear ownership (each doc has purpose)
- ✅ Easier to spot outdated content
- ✅ Reduced duplication

**Enhanced Onboarding:**
- ✅ New developers have clear entry point (docs/README.md)
- ✅ Contributors know where to add documentation
- ✅ Standard format reduces cognitive load
- ✅ Examples in templates guide writing

**Professional Appearance:**
- ✅ Well-organized documentation signals quality project
- ✅ Easier to showcase to stakeholders
- ✅ Better for open-source contributions
- ✅ Supports long-term maintenance

### Negative

**Migration Effort:**
- ❌ Time investment to move and consolidate files
- ❌ Risk of breaking existing links (mitigated by Phase 3 QA)
- ❌ Learning curve for new structure

**Ongoing Maintenance:**
- ❌ Must keep indexes updated
- ❌ Requires discipline to follow standards
- ❌ More files to maintain (READMEs, indexes)

### Mitigation Strategies

1. **Automated Link Checking**: Add CI job to verify all links
2. **Documentation Checklist**: Add to PR template
3. **Periodic Reviews**: Quarterly documentation audit
4. **Template Automation**: Scripts to generate skeleton docs

---

## Metrics for Success

**Quantitative:**
- Number of broken links: Target < 5
- Documentation coverage: 100% of major features documented
- Time to find documentation: < 2 minutes (via index)
- Outdated documents: < 10%

**Qualitative:**
- New developer onboarding feedback
- Contribution quality (fewer questions about "where to add docs")
- Stakeholder satisfaction with documentation quality

---

## Alternatives Considered

### Alternative 1: Keep Current Structure

**Pros:**
- No migration effort
- No broken links
- Familiarity for existing contributors

**Cons:**
- Continued discoverability problems
- Growing mess as more features added
- Hard to onboard new developers

**Rejected**: Technical debt will compound over time

### Alternative 2: Use External Documentation Platform (e.g., ReadTheDocs, Docusaurus)

**Pros:**
- Professional appearance
- Search functionality
- Version management
- Automatic generation

**Cons:**
- External dependency
- Setup and configuration overhead
- May be overkill for current needs
- Requires learning new tooling

**Rejected**: Markdown in Git is sufficient for current scale

### Alternative 3: Wiki-based Documentation

**Pros:**
- Easy editing
- Good for collaborative documentation
- Search functionality

**Cons:**
- Separate from code repository
- No version control integration
- Harder to review changes
- Risk of staleness

**Rejected**: Prefer documentation living with code

---

## Implementation Checklist

### Week 1: Structure
- [ ] Create directory structure (`docs/{features,operations,development,api}`)
- [ ] Create `docs/README.md` with index
- [ ] Create `docs/ADR/README.md` with ADR list
- [ ] Move feature documentation to `docs/features/`
- [ ] Move operational docs to `docs/operations/`
- [ ] Standardize ADR numbering (rename 009 → 0009)

### Week 2: Content
- [ ] Consolidate `RMA_QUICKSTART.md` + `RMA_TESTING.md` → `docs/features/rma-workflow.md`
- [ ] Consolidate `DOCKER.md` + `DOCKER_QUICKREF.txt` → `docs/operations/docker-setup.md`
- [ ] Create `docs/features/checkpoint4-features.md`
- [ ] Create `docs/development/CONTRIBUTING.md`
- [ ] Create `docs/development/testing-guide.md`
- [ ] Create `docs/api/rest-api.md`
- [ ] Update all cross-references to new paths

### Week 3: QA
- [ ] Run link checker on all markdown files
- [ ] Spell check all documentation
- [ ] Verify all ADRs follow template
- [ ] Review content for accuracy
- [ ] Test documentation paths with new developer
- [ ] Update root `README.md` with new structure

### Ongoing
- [ ] Add documentation check to PR template
- [ ] Set up CI job for link validation
- [ ] Schedule quarterly documentation review
- [ ] Create script to generate feature doc skeleton

---

## References

- [Architectural Decision Records](https://adr.github.io/)
- [Documentation Best Practices](https://www.writethedocs.org/guide/)
- [The Documentation System](https://documentation.divio.com/)
- [Markdown Style Guide](https://www.markdownguide.org/basic-syntax/)

---

## Related ADRs

- ADR-0021: Lightweight Features Design (documents recent additions)
- ADR-0020: RMA System Design (complex feature documentation example)
- ADR-0019: Observability Implementation (monitoring documentation)

---

## Appendix: File Mapping

### Before → After

```
# Root level docs → docs/features/
ADMIN_PAGES.md → docs/features/admin-interface.md
INVENTORY_LOGIC.md → docs/features/inventory-management.md
RMA_QUICKSTART.md + RMA_TESTING.md → docs/features/rma-workflow.md
RMA_IMPLEMENTATION_SUMMARY.md → docs/features/rma-workflow.md (merge)
RMA_API.md → docs/api/rma-api.md
RMA_METRICS_VIDEO_SCRIPT.md → docs/features/rma-metrics.md

# Root level ops docs → docs/operations/
DOCKER.md + DOCKER_QUICKREF.txt → docs/operations/docker-setup.md
DOCKER_TESTING.md → docs/operations/docker-testing.md

# Root level dev docs → docs/development/
[Create new] → docs/development/CONTRIBUTING.md
[Create new] → docs/development/testing-guide.md
[Create new] → docs/development/local-setup.md

# Keep in root
README.md (update to reference docs/)
requirements.txt
setup.py
Makefile
Dockerfile
docker-compose.yml
docker-entrypoint.sh
.gitignore
```

---

## Conclusion

This ADR establishes a sustainable documentation strategy that will:
1. Scale with project growth
2. Support multiple contributors
3. Reduce onboarding friction
4. Maintain professional standards
5. Enable long-term maintenance

**Implementation Timeline**: 3 weeks  
**Effort Estimate**: 16-24 hours total  
**Risk Level**: Low (mostly file moves and consolidation)  
**Impact**: High (significantly improves developer experience)

The structured approach ensures documentation remains a first-class concern in the project, not an afterthought.
