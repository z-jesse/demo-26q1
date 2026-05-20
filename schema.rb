# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[7.1].define(version: 2026_05_18_223103) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "plpgsql"

  # Custom types defined in this database.
  # Note that some types may not work with other database engines. Be careful if changing database.
  create_enum "bookable_template_status", ["pending", "active", "inactive"]
  create_enum "business_number_types", ["personal", "marketing"]
  create_enum "class_tag_status", ["active", "inactive"]
  create_enum "config_membership_refund_periods", ["none", "hour", "day", "week", "month", "year"]
  create_enum "customer_group_status", ["active", "inactive"]
  create_enum "email_address_statuses", ["active", "inactive"]
  create_enum "email_template_bulk_send_status", ["pending", "sent", "failed"]
  create_enum "membership_plan_intro_offer_types", ["none", "pre_booking", "pre_membership", "pre_self"]
  create_enum "membership_plan_refresh_periods", ["none", "day", "week", "month", "year"]
  create_enum "order_statuses", ["pending", "completed", "cancelled", "failed", "refunded"]
  create_enum "organization_invitation_statuses", ["pending", "accepted", "declined", "cancelled"]
  create_enum "product_statuses", ["active", "inactive"]
  create_enum "promotion_units", ["percent", "cents"]
  create_enum "stripe_account_status", ["pending", "active", "inactive"]
  create_enum "substitution_request_statuses", ["active", "cancelled", "completed"]
  create_enum "substitution_response_statuses", ["pending", "declined", "approved", "denied", "cancelled"]
  create_enum "terminal_order_status", ["pending", "completed", "failed", "cancelled"]
  create_enum "waiver_types", ["general", "membership"]

  create_table "ai_conversations", force: :cascade do |t|
    t.bigint "staff_profile_id", null: false
    t.string "public_id", null: false
    t.string "title", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_ai_conversations_on_public_id", unique: true
    t.index ["staff_profile_id"], name: "index_ai_conversations_on_staff_profile_id"
  end

  create_table "bookable_templates", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.text "description"
    t.text "image_data"
    t.integer "price_cents", default: 0
    t.boolean "hidden", default: false, null: false
    t.enum "status", default: "pending", enum_type: "bookable_template_status"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "color"
    t.integer "member_price_cents"
    t.index ["organization_id"], name: "index_bookable_templates_on_organization_id"
    t.index ["public_id"], name: "index_bookable_templates_on_public_id", unique: true
  end

  create_table "bookables", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "bookable_template_id", null: false
    t.bigint "recurrence_id"
    t.datetime "start_at", null: false
    t.datetime "end_at", null: false
    t.integer "capacity", limit: 2
    t.string "status", default: "pending"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "organization_id"
    t.bigint "staff_profile_id"
    t.bigint "space_id"
    t.bigint "spot_layout_id"
    t.boolean "unlisted", default: false
    t.bigint "cancellation_policy_id"
    t.index ["bookable_template_id"], name: "index_bookables_on_bookable_template_id"
    t.index ["end_at"], name: "index_bookables_on_end_at"
    t.index ["organization_id"], name: "index_bookables_on_organization_id"
    t.index ["public_id"], name: "index_bookables_on_public_id", unique: true
    t.index ["recurrence_id"], name: "index_bookables_on_recurrence_id"
    t.index ["space_id"], name: "index_bookables_on_space_id"
    t.index ["spot_layout_id"], name: "index_bookables_on_spot_layout_id"
    t.index ["staff_profile_id"], name: "index_bookables_on_staff_profile_id"
    t.index ["start_at"], name: "index_bookables_on_start_at"
  end

  create_table "bookings", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "customer_profile_id", null: false
    t.bigint "bookable_id", null: false
    t.string "status", default: "pending"
    t.datetime "cancelled_at"
    t.string "cancellation_reason"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.datetime "checked_in_at"
    t.bigint "promo_code_id"
    t.bigint "spot_element_id"
    t.bigint "host_booking_id"
    t.datetime "purchased_at"
    t.datetime "failed_at"
    t.string "payment_source_type"
    t.bigint "payment_source_id"
    t.index ["bookable_id"], name: "index_bookings_on_bookable_id"
    t.index ["customer_profile_id"], name: "index_bookings_on_customer_profile_id"
    t.index ["host_booking_id"], name: "index_bookings_on_host_booking_id"
    t.index ["payment_source_type", "payment_source_id"], name: "index_bookings_on_payment_source"
    t.index ["promo_code_id"], name: "index_bookings_on_promo_code_id"
    t.index ["public_id"], name: "index_bookings_on_public_id", unique: true
    t.index ["spot_element_id"], name: "index_bookings_on_spot_element_id"
  end

  create_table "branch_links", force: :cascade do |t|
    t.bigint "branch_id", null: false
    t.bigint "branch_group_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "branches", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.string "address_line_1"
    t.string "address_line_2"
    t.string "city", null: false
    t.string "state", null: false
    t.string "zip", null: false
    t.string "phone_number"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "country", default: "US", null: false
    t.index ["public_id"], name: "index_branches_on_public_id", unique: true
  end

  create_table "business_numbers", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "number", null: false
    t.enum "phone_type", enum_type: "business_number_types"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_business_numbers_on_organization_id"
  end

  create_table "cancellation_policies", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.integer "cancellation_window_minutes"
    t.integer "late_cancellation_fee_cents", default: 1000, null: false
    t.integer "no_show_fee_cents", default: 2000, null: false
    t.string "refund_type"
    t.string "non_credit_refund_type"
    t.string "status", default: "active", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_cancellation_policies_on_organization_id"
    t.index ["public_id"], name: "index_cancellation_policies_on_public_id", unique: true
  end

  create_table "card_payments", force: :cascade do |t|
    t.bigint "stripe_card_id"
    t.bigint "organization_id"
    t.string "stripe_payment_intent_id"
    t.string "status"
    t.json "raw"
    t.string "client_secret"
    t.integer "amount_cents"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "user_id"
    t.index ["organization_id"], name: "index_card_payments_on_organization_id"
    t.index ["stripe_card_id"], name: "index_card_payments_on_stripe_card_id"
    t.index ["user_id"], name: "index_card_payments_on_user_id"
  end

  create_table "class_tag_links", force: :cascade do |t|
    t.bigint "class_tag_id", null: false
    t.bigint "staff_profile_id"
    t.bigint "bookable_template_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["bookable_template_id"], name: "index_class_tag_links_on_bookable_template_id"
  end

  create_table "class_tags", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.text "description"
    t.enum "status", default: "active", enum_type: "class_tag_status"
    t.string "public_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "color", null: false
    t.index ["public_id"], name: "index_class_tags_on_public_id", unique: true
  end

  create_table "class_voucher_wallets", force: :cascade do |t|
    t.bigint "customer_profile_id", null: false
    t.string "public_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["customer_profile_id"], name: "index_class_voucher_wallets_on_customer_profile_id"
    t.index ["public_id"], name: "index_class_voucher_wallets_on_public_id", unique: true
  end

  create_table "class_vouchers", force: :cascade do |t|
    t.bigint "class_voucher_wallet_id"
    t.bigint "guest_pass_wallet_id"
    t.bigint "booking_id"
    t.datetime "expires_at"
    t.datetime "redeemed_at"
    t.datetime "cancelled_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "public_id", null: false
    t.string "source_type"
    t.bigint "source_id"
    t.index ["booking_id"], name: "index_class_vouchers_on_booking_id"
    t.index ["class_voucher_wallet_id"], name: "index_class_vouchers_on_class_voucher_wallet_id"
    t.index ["guest_pass_wallet_id"], name: "index_class_vouchers_on_guest_pass_wallet_id"
    t.index ["public_id"], name: "index_class_vouchers_on_public_id", unique: true
    t.index ["source_type", "source_id"], name: "index_class_vouchers_on_source"
  end

  create_table "customer_groups", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "name"
    t.string "public_id", null: false
    t.text "special_sql"
    t.string "dynamic_params", default: [], array: true
    t.enum "status", default: "active", enum_type: "customer_group_status"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_customer_groups_on_organization_id"
    t.index ["public_id"], name: "index_customer_groups_on_public_id", unique: true
  end

  create_table "customer_profiles", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "organization_id"
    t.string "public_id"
    t.index ["organization_id"], name: "index_customer_profiles_on_organization_id"
    t.index ["public_id"], name: "index_customer_profiles_on_public_id", unique: true
    t.index ["user_id"], name: "index_customer_profiles_on_user_id"
  end

  create_table "detailed_customer_groups", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "customer_group_id", null: false
    t.string "raw_sql"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["customer_group_id"], name: "index_detailed_customer_groups_on_customer_group_id"
    t.index ["public_id"], name: "index_detailed_customer_groups_on_public_id", unique: true
  end

  create_table "email_addresses", force: :cascade do |t|
    t.bigint "organization_config_id", null: false
    t.string "handle", null: false
    t.string "sender_name"
    t.boolean "default", default: false
    t.string "public_id", null: false
    t.enum "status", default: "active", null: false, enum_type: "email_address_statuses"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_config_id"], name: "index_email_addresses_on_organization_config_id"
    t.index ["public_id"], name: "index_email_addresses_on_public_id", unique: true
  end

  create_table "email_messages", force: :cascade do |t|
    t.bigint "customer_profile_id"
    t.bigint "organization_id"
    t.text "raw"
    t.string "reply_to"
    t.string "from"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "email_template_bulk_sends", force: :cascade do |t|
    t.string "public_id", null: false
    t.string "name", null: false
    t.bigint "email_template_version_id", null: false
    t.bigint "detailed_customer_group_id", null: false
    t.datetime "send_at"
    t.enum "status", default: "pending", null: false, enum_type: "email_template_bulk_send_status"
    t.string "subject_line"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "email_address_id"
    t.index ["email_address_id"], name: "index_email_template_bulk_sends_on_email_address_id"
    t.index ["email_template_version_id"], name: "index_email_template_bulk_sends_on_email_template_version_id"
    t.index ["public_id"], name: "index_email_template_bulk_sends_on_public_id", unique: true
  end

  create_table "email_template_images", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.text "image_data", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "email_template_sends", force: :cascade do |t|
    t.bigint "email_template_bulk_send_id", null: false
    t.bigint "customer_profile_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "sendgrid_message_id"
    t.datetime "opened_at"
    t.datetime "bounced_at"
    t.string "public_id", null: false
    t.index ["customer_profile_id"], name: "index_email_template_sends_on_customer_profile_id"
    t.index ["email_template_bulk_send_id"], name: "index_email_template_sends_on_email_template_bulk_send_id"
    t.index ["public_id"], name: "index_email_template_sends_on_public_id", unique: true
    t.index ["sendgrid_message_id"], name: "index_email_template_sends_on_sendgrid_message_id", unique: true
  end

  create_table "email_template_transaction_sends", force: :cascade do |t|
    t.bigint "email_template_version_id", null: false
    t.bigint "customer_profile_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "sendgrid_message_id"
    t.datetime "bounced_at"
    t.datetime "opened_at"
    t.string "public_id", null: false
    t.bigint "staff_profile_id"
    t.index ["customer_profile_id"], name: "index_email_template_transaction_sends_on_customer_profile_id"
    t.index ["email_template_version_id"], name: "idx_on_email_template_version_id_c7d09dd0dd"
    t.index ["public_id"], name: "index_email_template_transaction_sends_on_public_id", unique: true
    t.index ["sendgrid_message_id"], name: "index_email_template_transaction_sends_on_sendgrid_message_id", unique: true
    t.index ["staff_profile_id"], name: "index_email_template_transaction_sends_on_staff_profile_id"
  end

  create_table "email_template_versions", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "email_template_id", null: false
    t.string "change_description"
    t.json "content_json"
    t.text "content_html"
    t.bigint "last_editor_id"
    t.datetime "saved_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["email_template_id"], name: "index_email_template_versions_on_email_template_id"
    t.index ["last_editor_id"], name: "index_email_template_versions_on_last_editor_id"
    t.index ["public_id"], name: "index_email_template_versions_on_public_id", unique: true
    t.index ["saved_at"], name: "index_email_template_versions_on_saved_at"
  end

  create_table "email_templates", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_email_templates_on_organization_id"
    t.index ["public_id"], name: "index_email_templates_on_public_id", unique: true
  end

  create_table "guest_pass_wallets", force: :cascade do |t|
    t.bigint "customer_profile_id"
    t.string "public_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["customer_profile_id"], name: "index_guest_pass_wallets_on_customer_profile_id"
    t.index ["public_id"], name: "index_guest_pass_wallets_on_public_id", unique: true
  end

  create_table "late_cancellation_fees", force: :cascade do |t|
    t.bigint "booking_id"
    t.bigint "organization_id"
    t.integer "price_cents", null: false
    t.string "fee_subject"
    t.datetime "paid_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "payment_source_type"
    t.bigint "payment_source_id"
    t.index ["booking_id"], name: "index_late_cancellation_fees_on_booking_id"
    t.index ["organization_id"], name: "index_late_cancellation_fees_on_organization_id"
    t.index ["payment_source_type", "payment_source_id"], name: "index_late_cancellation_fees_on_payment_source"
  end

  create_table "membership_plans", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "public_id", null: false
    t.integer "price_cents", default: 0, null: false
    t.string "name", null: false
    t.string "status", default: "active", null: false
    t.string "description"
    t.enum "intro_offer_type", enum_type: "membership_plan_intro_offer_types"
    t.integer "refresh_period_amount"
    t.enum "refresh_period_unit", default: "none", enum_type: "membership_plan_refresh_periods"
    t.integer "class_limit", default: 0
    t.integer "class_limit_period_amount"
    t.enum "class_limit_period_unit", default: "none", enum_type: "membership_plan_refresh_periods"
    t.integer "guest_pass_count", default: 0
    t.integer "guest_pass_period_amount"
    t.enum "guest_pass_period_unit", default: "none", enum_type: "membership_plan_refresh_periods"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.integer "max_stock"
    t.integer "display_order"
    t.boolean "unlisted", default: false, null: false
    t.index ["organization_id"], name: "index_membership_plans_on_organization_id"
    t.index ["public_id"], name: "index_membership_plans_on_public_id", unique: true
  end

  create_table "memberships", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "customer_profile_id", null: false
    t.bigint "membership_plan_id", null: false
    t.datetime "activated_at"
    t.datetime "expires_at"
    t.datetime "cancelled_at"
    t.datetime "classes_expire_at"
    t.datetime "guest_passes_expire_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.datetime "purchased_at"
    t.bigint "promo_code_id"
    t.datetime "failed_at"
    t.string "payment_source_type"
    t.bigint "payment_source_id"
    t.index ["customer_profile_id"], name: "index_memberships_on_customer_profile_id"
    t.index ["membership_plan_id"], name: "index_memberships_on_membership_plan_id"
    t.index ["payment_source_type", "payment_source_id"], name: "index_memberships_on_payment_source"
    t.index ["promo_code_id"], name: "index_memberships_on_promo_code_id"
    t.index ["public_id"], name: "index_memberships_on_public_id", unique: true
  end

  create_table "memberships_renewals", force: :cascade do |t|
    t.bigint "membership_id", null: false
    t.date "billing_start_date", null: false
    t.date "billing_end_date", null: false
    t.datetime "purchased_at"
    t.bigint "promo_code_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "public_id", null: false
    t.datetime "failed_at"
    t.string "payment_source_type"
    t.bigint "payment_source_id"
    t.index ["membership_id"], name: "index_memberships_renewals_on_membership_id"
    t.index ["payment_source_type", "payment_source_id"], name: "index_memberships_renewals_on_payment_source"
    t.index ["promo_code_id"], name: "index_memberships_renewals_on_promo_code_id"
    t.index ["public_id"], name: "index_memberships_renewals_on_public_id", unique: true
  end

  create_table "merchant_details", force: :cascade do |t|
    t.bigint "stripe_card_id", null: false
    t.bigint "stripe_account_id", null: false
    t.string "stripe_payment_method_id", null: false
    t.string "stripe_customer_id", null: false
    t.json "raw"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "organization_configs", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.enum "membership_refund_period", default: "none", enum_type: "config_membership_refund_periods"
    t.integer "membership_refund_period_amount"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.boolean "delayed_membership", default: false, null: false
    t.string "marketing_email"
    t.string "marketing_email_domain"
    t.string "timezone", default: "UTC", null: false
    t.string "meta_conversions_pixel_id"
    t.string "meta_conversions_access_token"
    t.string "default_pay_period_rrule"
    t.string "google_analytics_measurement_id"
    t.string "google_analytics_api_secret"
    t.string "terms_url"
    t.string "privacy_url"
    t.boolean "enable_sms", default: false, null: false
    t.bigint "default_cancellation_policy_id"
    t.boolean "allow_discover", default: true, null: false
    t.index ["default_cancellation_policy_id"], name: "index_organization_configs_on_default_cancellation_policy_id"
    t.index ["organization_id"], name: "index_organization_configs_on_organization_id"
  end

  create_table "organization_invitations", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.enum "status", default: "pending", enum_type: "organization_invitation_statuses"
    t.string "email", null: false
    t.string "role", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "staff_profile_id"
    t.index ["email"], name: "index_organization_invitations_on_email"
    t.index ["public_id"], name: "index_organization_invitations_on_public_id", unique: true
    t.index ["staff_profile_id"], name: "index_organization_invitations_on_staff_profile_id"
  end

  create_table "organizations", force: :cascade do |t|
    t.string "public_id", null: false
    t.string "name", null: false
    t.string "email", null: false
    t.string "phone_number"
    t.string "website_url"
    t.text "description_md"
    t.text "image_data"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_organizations_on_public_id", unique: true
  end

  create_table "password_reset_requests", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "reset_token", null: false
    t.datetime "claimed_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["reset_token"], name: "index_password_reset_requests_on_reset_token", unique: true
    t.index ["user_id"], name: "index_password_reset_requests_on_user_id"
  end

  create_table "payment_methods", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "status", default: "active", null: false
    t.boolean "default", default: false, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "method_details_id", null: false
    t.string "method_details_type", null: false
    t.string "public_id"
    t.index ["public_id"], name: "index_payment_methods_on_public_id", unique: true
    t.index ["user_id"], name: "index_payment_methods_on_user_id"
  end

  create_table "payments", force: :cascade do |t|
    t.bigint "user_id"
    t.bigint "payment_method_id"
    t.string "purchasable_type", null: false
    t.bigint "purchasable_id", null: false
    t.string "payment_details_type"
    t.bigint "payment_details_id"
    t.bigint "terminal_order_id"
    t.string "status", default: "pending", null: false
    t.integer "amount_cents", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["payment_details_type", "payment_details_id"], name: "index_payments_on_payment_details"
    t.index ["payment_method_id"], name: "index_payments_on_payment_method_id"
    t.index ["purchasable_type", "purchasable_id"], name: "index_payments_on_purchasable"
    t.index ["terminal_order_id"], name: "index_payments_on_terminal_order_id"
    t.index ["user_id"], name: "index_payments_on_user_id"
  end

  create_table "product_orders", force: :cascade do |t|
    t.bigint "product_id", null: false
    t.bigint "customer_profile_id"
    t.enum "status", default: "pending", null: false, enum_type: "order_statuses"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "promo_code_id"
    t.string "public_id", null: false
    t.datetime "purchased_at"
    t.datetime "failed_at"
    t.string "payment_source_type"
    t.bigint "payment_source_id"
    t.index ["customer_profile_id"], name: "index_product_orders_on_customer_profile_id"
    t.index ["payment_source_type", "payment_source_id"], name: "index_product_orders_on_payment_source"
    t.index ["product_id"], name: "index_product_orders_on_product_id"
    t.index ["promo_code_id"], name: "index_product_orders_on_promo_code_id"
    t.index ["public_id"], name: "index_product_orders_on_public_id", unique: true
  end

  create_table "products", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.string "description"
    t.string "public_id", null: false
    t.enum "status", default: "active", null: false, enum_type: "product_statuses"
    t.integer "price_cents", null: false
    t.integer "stock"
    t.text "image_data"
    t.string "sku"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_products_on_organization_id"
    t.index ["public_id"], name: "index_products_on_public_id", unique: true
  end

  create_table "promo_codes", force: :cascade do |t|
    t.bigint "promotion_id", null: false
    t.string "public_id", null: false
    t.string "code", null: false
    t.datetime "valid_from", null: false
    t.datetime "valid_to"
    t.integer "uses"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["code"], name: "index_promo_codes_on_code"
    t.index ["promotion_id"], name: "index_promo_codes_on_promotion_id"
    t.index ["public_id"], name: "index_promo_codes_on_public_id", unique: true
  end

  create_table "promotions", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "public_id", null: false
    t.string "name", null: false
    t.enum "unit", null: false, enum_type: "promotion_units"
    t.integer "value", null: false
    t.datetime "start_at"
    t.datetime "end_at"
    t.interval "duration"
    t.jsonb "item_types", default: {"booking"=>true, "product"=>true, "membership"=>true}, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_promotions_on_organization_id"
    t.index ["public_id"], name: "index_promotions_on_public_id", unique: true
  end

  create_table "recurrences", force: :cascade do |t|
    t.bigint "bookable_template_id", null: false
    t.string "public_id", null: false
    t.bigint "staff_profile_id"
    t.datetime "start_at", null: false
    t.string "status", default: "pending"
    t.integer "capacity"
    t.string "rrule", null: false
    t.integer "duration_minutes", null: false
    t.datetime "until"
    t.integer "remaining_count"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "organization_id"
    t.bigint "space_id"
    t.bigint "spot_layout_id"
    t.boolean "unlisted", default: false
    t.bigint "cancellation_policy_id"
    t.index ["cancellation_policy_id"], name: "index_recurrences_on_cancellation_policy_id"
    t.index ["organization_id"], name: "index_recurrences_on_organization_id"
    t.index ["public_id"], name: "index_recurrences_on_public_id", unique: true
    t.index ["space_id"], name: "index_recurrences_on_space_id"
    t.index ["staff_profile_id"], name: "index_recurrences_on_staff_profile_id"
  end

  create_table "refresh_tokens", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "jti", null: false
    t.datetime "expires_at", null: false
    t.datetime "revoked_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["jti"], name: "index_refresh_tokens_on_jti"
    t.index ["user_id"], name: "index_refresh_tokens_on_user_id"
  end

  create_table "saved_guests", force: :cascade do |t|
    t.bigint "customer_id", null: false
    t.bigint "guest_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["customer_id"], name: "index_saved_guests_on_customer_id"
    t.index ["guest_id"], name: "index_saved_guests_on_guest_id"
  end

  create_table "sms_chats", force: :cascade do |t|
    t.bigint "customer_profile_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "public_id", null: false
    t.index ["public_id"], name: "index_sms_chats_on_public_id", unique: true
  end

  create_table "sms_messages", force: :cascade do |t|
    t.string "public_id", null: false
    t.text "body", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.datetime "delivered_at"
    t.datetime "failed_at"
    t.string "sender_type"
    t.bigint "sender_id"
    t.string "telnyx_message_id"
    t.bigint "sms_chat_id", null: false
    t.string "message_type", default: "direct", null: false
    t.bigint "sms_template_version_id"
    t.index ["public_id"], name: "index_sms_messages_on_public_id", unique: true
    t.index ["sms_chat_id", "created_at"], name: "index_sms_messages_on_sms_chat_id_and_created_at", order: { created_at: :desc }
    t.index ["sms_template_version_id"], name: "index_sms_messages_on_sms_template_version_id"
    t.index ["telnyx_message_id"], name: "index_sms_messages_on_telnyx_message_id"
  end

  create_table "sms_read_receipts", force: :cascade do |t|
    t.bigint "sms_chat_id", null: false
    t.bigint "last_read_message_id"
    t.bigint "staff_profile_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["sms_chat_id"], name: "index_sms_read_receipts_on_sms_chat_id"
    t.index ["staff_profile_id"], name: "index_sms_read_receipts_on_staff_profile_id"
  end

  create_table "sms_template_versions", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "sms_template_id", null: false
    t.string "change_description"
    t.text "content_text"
    t.bigint "last_editor_id"
    t.datetime "saved_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["last_editor_id"], name: "index_sms_template_versions_on_last_editor_id"
    t.index ["public_id"], name: "index_sms_template_versions_on_public_id", unique: true
    t.index ["saved_at"], name: "index_sms_template_versions_on_saved_at"
    t.index ["sms_template_id"], name: "index_sms_template_versions_on_sms_template_id"
  end

  create_table "sms_templates", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_sms_templates_on_organization_id"
    t.index ["public_id"], name: "index_sms_templates_on_public_id", unique: true
  end

  create_table "spaces", force: :cascade do |t|
    t.bigint "branch_id", null: false
    t.string "name"
    t.string "public_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["branch_id"], name: "index_spaces_on_branch_id"
    t.index ["public_id"], name: "index_spaces_on_public_id", unique: true
  end

  create_table "spot_booking_components", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id"
    t.string "name"
    t.text "image_data", null: false
    t.boolean "preserve_aspect_ratio", default: false, null: false
    t.integer "default_width", null: false
    t.integer "default_height", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_spot_booking_components_on_organization_id"
    t.index ["public_id"], name: "index_spot_booking_components_on_public_id", unique: true
  end

  create_table "spot_booking_elements", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "layout_id", null: false
    t.bigint "component_id", null: false
    t.string "label"
    t.float "x", null: false
    t.float "y", null: false
    t.float "width", null: false
    t.float "height", null: false
    t.boolean "is_bookable", default: false, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["component_id"], name: "index_spot_booking_elements_on_component_id"
    t.index ["layout_id"], name: "index_spot_booking_elements_on_layout_id"
    t.index ["public_id"], name: "index_spot_booking_elements_on_public_id", unique: true
  end

  create_table "spot_booking_layouts", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "organization_id", null: false
    t.string "name"
    t.float "width", null: false
    t.float "height", null: false
    t.integer "grid_snap"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_spot_booking_layouts_on_organization_id"
    t.index ["public_id"], name: "index_spot_booking_layouts_on_public_id", unique: true
  end

  create_table "staff_credit_grants", force: :cascade do |t|
    t.string "public_id", null: false
    t.bigint "staff_profile_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_staff_credit_grants_on_public_id", unique: true
    t.index ["staff_profile_id"], name: "index_staff_credit_grants_on_staff_profile_id"
  end

  create_table "staff_profiles", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.bigint "organization_id", null: false
    t.string "role", default: "staff", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "public_id"
    t.text "description"
    t.index ["organization_id"], name: "index_staff_profiles_on_organization_id"
    t.index ["public_id"], name: "index_staff_profiles_on_public_id", unique: true
    t.index ["user_id", "organization_id"], name: "index_staff_profiles_on_user_id_and_organization_id", unique: true
  end

  create_table "stripe_accounts", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "stripe_account_id"
    t.enum "status", default: "pending", null: false, enum_type: "stripe_account_status"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.jsonb "raw"
    t.index ["organization_id"], name: "index_stripe_accounts_on_organization_id", unique: true
  end

  create_table "stripe_cards", force: :cascade do |t|
    t.bigint "stripe_customer_id", null: false
    t.string "stripe_payment_method_id", null: false
    t.string "fingerprint", null: false
    t.json "raw"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["stripe_customer_id", "fingerprint"], name: "index_stripe_cards_on_stripe_customer_id_and_fingerprint", unique: true
    t.index ["stripe_customer_id"], name: "index_stripe_cards_on_stripe_customer_id"
    t.index ["stripe_payment_method_id"], name: "index_stripe_cards_on_stripe_payment_method_id", unique: true
  end

  create_table "stripe_customers", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "stripe_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["stripe_id"], name: "index_stripe_customers_on_stripe_id", unique: true
    t.index ["user_id"], name: "index_stripe_customers_on_user_id", unique: true
  end

  create_table "stripe_locations", force: :cascade do |t|
    t.bigint "branch_id", null: false
    t.string "stripe_id", null: false
    t.jsonb "raw"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["stripe_id"], name: "index_stripe_locations_on_stripe_id", unique: true
  end

  create_table "stripe_terminals", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.bigint "stripe_location_id", null: false
    t.string "terminal_identifier", null: false
    t.string "public_id", null: false
    t.string "name", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_stripe_terminals_on_public_id", unique: true
  end

  create_table "substitution_requests", force: :cascade do |t|
    t.bigint "bookable_id", null: false
    t.bigint "staff_profile_id", null: false
    t.string "public_id", null: false
    t.enum "status", default: "active", null: false, enum_type: "substitution_request_statuses"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["bookable_id"], name: "index_substitution_requests_on_bookable_id"
    t.index ["public_id"], name: "index_substitution_requests_on_public_id", unique: true
    t.index ["staff_profile_id"], name: "index_substitution_requests_on_staff_profile_id"
  end

  create_table "substitution_responses", force: :cascade do |t|
    t.bigint "substitution_request_id", null: false
    t.bigint "staff_profile_id", null: false
    t.string "public_id", null: false
    t.enum "status", default: "pending", null: false, enum_type: "substitution_response_statuses"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_substitution_responses_on_public_id", unique: true
    t.index ["staff_profile_id"], name: "index_substitution_responses_on_staff_profile_id"
    t.index ["substitution_request_id"], name: "index_substitution_responses_on_substitution_request_id"
  end

  create_table "tax_settings", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.decimal "booking_tax_rate", precision: 6, scale: 3, default: "0.0", null: false
    t.decimal "product_tax_rate", precision: 6, scale: 3, default: "0.0", null: false
    t.decimal "membership_tax_rate", precision: 6, scale: 3, default: "0.0", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_tax_settings_on_organization_id", unique: true
  end

  create_table "telnyx_webhook_messages", force: :cascade do |t|
    t.jsonb "payload"
    t.string "event_type"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "message_id"
    t.index ["message_id"], name: "index_telnyx_webhook_messages_on_message_id"
  end

  create_table "terminal_follow_up_orders", force: :cascade do |t|
    t.bigint "terminal_order_id", null: false
    t.datetime "fulfilled_at"
    t.jsonb "raw_order"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["terminal_order_id"], name: "index_terminal_follow_up_orders_on_terminal_order_id"
  end

  create_table "terminal_orders", force: :cascade do |t|
    t.bigint "user_id"
    t.bigint "organization_id"
    t.integer "amount_cents"
    t.string "stripe_payment_intent_identifier"
    t.enum "status", default: "pending", enum_type: "terminal_order_status"
    t.string "public_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "stripe_terminal_id", null: false
    t.string "latest_failure"
    t.index ["organization_id"], name: "index_terminal_orders_on_organization_id"
    t.index ["public_id"], name: "index_terminal_orders_on_public_id", unique: true
    t.index ["stripe_payment_intent_identifier"], name: "index_terminal_orders_on_stripe_payment_intent_identifier"
    t.index ["user_id"], name: "index_terminal_orders_on_user_id"
  end

  create_table "transactional_email_templates", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.boolean "enabled", default: false, null: false
    t.string "public_id", null: false
    t.string "transaction_name", null: false
    t.string "subject"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.bigint "email_template_id"
    t.index ["email_template_id"], name: "index_transactional_email_templates_on_email_template_id"
    t.index ["organization_id"], name: "index_transactional_email_templates_on_organization_id"
    t.index ["public_id"], name: "index_transactional_email_templates_on_public_id", unique: true
    t.index ["transaction_name"], name: "index_transactional_email_templates_on_transaction_name"
  end

  create_table "transactional_sms_templates", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.boolean "enabled", default: false, null: false
    t.string "public_id", null: false
    t.string "transaction_name", null: false
    t.bigint "sms_template_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["organization_id"], name: "index_transactional_sms_templates_on_organization_id"
    t.index ["public_id"], name: "index_transactional_sms_templates_on_public_id", unique: true
    t.index ["sms_template_id"], name: "index_transactional_sms_templates_on_sms_template_id"
    t.index ["transaction_name"], name: "index_transactional_sms_templates_on_transaction_name"
  end

  create_table "unsubscribe_tags", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.bigint "customer_profile_id", null: false
    t.bigint "email_template_bulk_send_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["customer_profile_id"], name: "index_unsubscribe_tags_on_customer_profile_id"
    t.index ["email_template_bulk_send_id"], name: "index_unsubscribe_tags_on_email_template_bulk_send_id"
    t.index ["organization_id"], name: "index_unsubscribe_tags_on_organization_id"
  end

  create_table "user_fields_overrides", force: :cascade do |t|
    t.string "profile_type", null: false
    t.bigint "profile_id", null: false
    t.string "first_name"
    t.string "middle_name"
    t.string "last_name"
    t.text "image_data"
    t.string "phone"
    t.string "email"
    t.index ["profile_type", "profile_id"], name: "index_user_fields_overrides_on_profile", unique: true
  end

  create_table "user_prompts", force: :cascade do |t|
    t.bigint "conversation_id", null: false
    t.string "public_id", null: false
    t.string "question", null: false
    t.string "explanation"
    t.string "data_type"
    t.jsonb "outputs"
    t.jsonb "queries"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["conversation_id"], name: "index_user_prompts_on_conversation_id"
    t.index ["public_id"], name: "index_user_prompts_on_public_id", unique: true
  end

  create_table "users", force: :cascade do |t|
    t.string "public_id", null: false
    t.string "email", null: false
    t.string "password_digest"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.text "image_data"
    t.string "first_name"
    t.string "last_name"
    t.string "middle_name"
    t.string "phone"
    t.string "google_id"
    t.datetime "password_updated_at"
    t.datetime "last_google_sign_in_at"
    t.index ["email"], name: "index_users_on_email", unique: true
    t.index ["google_id"], name: "index_users_on_google_id", unique: true
    t.index ["public_id"], name: "index_users_on_public_id", unique: true
  end

  create_table "waitlist_entries", force: :cascade do |t|
    t.bigint "booking_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["booking_id"], name: "index_waitlist_entries_on_booking_id"
  end

  create_table "waiver_documents", force: :cascade do |t|
    t.bigint "waiver_id", null: false
    t.bigint "staff_profile_id"
    t.string "name", null: false
    t.text "description"
    t.text "document_data"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "waiver_signatures", force: :cascade do |t|
    t.bigint "waiver_id", null: false
    t.bigint "waiver_document_id", null: false
    t.bigint "customer_profile_id", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "public_id", null: false
    t.index ["public_id"], name: "index_waiver_signatures_on_public_id", unique: true
  end

  create_table "waivers", force: :cascade do |t|
    t.bigint "organization_id", null: false
    t.string "public_id", null: false
    t.enum "waiver_type", null: false, enum_type: "waiver_types"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["public_id"], name: "index_waivers_on_public_id", unique: true
  end

  add_foreign_key "email_template_transaction_sends", "staff_profiles"
  add_foreign_key "recurrences", "cancellation_policies"
end
